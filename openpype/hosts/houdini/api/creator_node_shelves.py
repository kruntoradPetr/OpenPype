"""Library to register OpenPype Creators for Houdini TAB node search menu.

This can be used to install custom houdini tools for the TAB search
menu which will trigger a publish instance to be created interactively.

The Creators are automatically registered on launch of Houdini through the
Houdini integration's `host.install()` method.

"""
import contextlib
import tempfile
import logging
import os

from openpype.pipeline import registered_host
from openpype.pipeline.create import CreateContext
from openpype.resources import get_openpype_icon_filepath

import hou

log = logging.getLogger(__name__)

CREATE_SCRIPT = """
from openpype.hosts.houdini.api.creator_node_shelves import create_interactive
create_interactive("{identifier}")
"""


def create_interactive(creator_identifier):
    """Create a Creator using its identifier interactively.

    This is used by the generated shelf tools as callback when a user selects
    the creator from the node tab search menu.

    Args:
        creator_identifier (str): The creator identifier of the Creator plugin
            to create.

    Return:
        list: The created instances.

    """

    # TODO Use Qt instead
    result, variant = hou.ui.readInput('Define variant name',
                                       buttons=("Ok", "Cancel"),
                                       initial_contents='Main',
                                       title="Define variant",
                                       help="Set the variant for the "
                                            "publish instance",
                                       close_choice=1)
    if result == 1:
        # User interrupted
        return
    variant = variant.strip()
    if not variant:
        raise RuntimeError("Empty variant value entered.")

    host = registered_host()
    context = CreateContext(host)

    before = context.instances_by_id.copy()

    # Create the instance
    context.create(
        creator_identifier=creator_identifier,
        variant=variant,
        pre_create_data={"use_selection": True}
    )

    # For convenience we set the new node as current since that's much more
    # familiar to the artist when creating a node interactively
    # TODO Allow to disable auto-select in studio settings or user preferences
    after = context.instances_by_id
    new = set(after) - set(before)
    if new:
        # Select the new instance
        for instance_id in new:
            instance = after[instance_id]
            node = hou.node(instance.get("instance_node"))
            node.setCurrent(True)

    return list(new)


@contextlib.contextmanager
def shelves_change_block():
    """Write shelf changes at the end of the context."""
    hou.shelves.beginChangeBlock()
    try:
        yield
    finally:
        hou.shelves.endChangeBlock()


def install():
    """Install the Creator plug-ins to show in Houdini's TAB node search menu.

    This function is re-entrant and can be called again to reinstall and
    update the node definitions. For example during development it can be
    useful to call it manually:
        >>> from openpype.hosts.houdini.api.creator_node_shelves import install
        >>> install()

    Returns:
        list: List of `hou.Tool` instances

    """

    host = registered_host()

    # Store the filepath on the host
    # TODO: Define a less hacky static shelf path for current houdini session
    filepath_attr = "_creator_node_shelf_filepath"
    filepath = getattr(host, filepath_attr, None)
    if filepath is None:
        f = tempfile.NamedTemporaryFile(prefix="houdini_creator_nodes_",
                                        suffix=".shelf",
                                        delete=False)
        f.close()
        filepath = f.name
        setattr(host, filepath_attr, filepath)
    elif os.path.exists(filepath):
        # Remove any existing shelf file so that we can completey regenerate
        # and update the tools file if creator identifiers change
        os.remove(filepath)

    icon = get_openpype_icon_filepath()

    # Create context only to get creator plugins, so we don't reset and only
    # populate what we need to retrieve the list of creator plugins
    create_context = CreateContext(host, reset=False)
    create_context.reset_current_context()
    create_context._reset_creator_plugins()

    log.debug("Writing OpenPype Creator nodes to shelf: {}".format(filepath))
    tools = []
    with shelves_change_block():
        for identifier, creator in create_context.manual_creators.items():

            # TODO: Allow the creator plug-in itself to override the categories
            #       for where they are shown, by e.g. defining
            #       `Creator.get_network_categories()`

            key = "openpype_create.{}".format(identifier)
            log.debug(f"Registering {key}")
            script = CREATE_SCRIPT.format(identifier=identifier)
            data = {
                "script": script,
                "language": hou.scriptLanguage.Python,
                "icon": icon,
                "help": "Create OpenPype publish instance for {}".format(
                    creator.label
                ),
                "help_url": None,
                "network_categories": [
                    hou.ropNodeTypeCategory(),
                    hou.sopNodeTypeCategory()
                ],
                "viewer_categories": [],
                "cop_viewer_categories": [],
                "network_op_type": None,
                "viewer_op_type": None,
                "locations": ["OpenPype"]
            }

            label = "Create {}".format(creator.label)
            tool = hou.shelves.tool(key)
            if tool:
                tool.setData(**data)
                tool.setLabel(label)
            else:
                tool = hou.shelves.newTool(
                    file_path=filepath,
                    name=key,
                    label=label,
                    **data
                )

            tools.append(tool)

    # Ensure the shelf is reloaded
    hou.shelves.loadFile(filepath)

    return tools
