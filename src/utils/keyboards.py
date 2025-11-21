from telethon import Button


def build_entry_buttons(
    entry_id: str,
    mode: str,
    index: int,
    total_entries: int,
    messages: dict,
) -> list:
    """
    Build inline keyboard for entry navigation.
    
    Args:
        entry_id: Entry UUID
        mode: "before" or "after"
        index: Current entry index (0-based)
        total_entries: Total number of entries
        messages: Localized messages dict
        
    Returns:
        List of button rows for Telethon
    """
    buttons = []
    
    # Mode row
    is_before = (mode == "before")
    before_text = f"✓ {messages['before_label']}" if is_before else messages['before_label']
    after_text = f"✓ {messages['after_label']}" if not is_before else messages['after_label']
    
    mode_row = []
    mode_row.append(Button.inline(
        before_text,
        data=f"ENTRY:{entry_id}:MODE:before:INDEX:{index}"
    ))
    mode_row.append(Button.inline(
        after_text,
        data=f"ENTRY:{entry_id}:MODE:after:INDEX:{index}"
    ))
    buttons.append(mode_row)
    
    # Navigation row
    nav_row = []
    if index > 0:
        nav_row.append(Button.inline(
            f"← {messages['prev_label']}",
            data=f"ENTRY:{entry_id}:MODE:{mode}:INDEX:{index - 1}"
        ))
    
    if index < total_entries - 1:
        nav_row.append(Button.inline(
            f"{messages['next_label']} →",
            data=f"ENTRY:{entry_id}:MODE:{mode}:INDEX:{index + 1}"
        ))
    
    if nav_row:
        buttons.append(nav_row)
    
    return buttons


def build_history_navigation_keyboard(
    entry_index: int,
    total_entries: int,
    is_before: bool,
    messages: dict,
) -> list:
    """Legacy function - kept for compatibility."""
    buttons = []
    
    mode_row = []
    before_text = f"✓ {messages['before_label']}" if is_before else messages['before_label']
    after_text = f"✓ {messages['after_label']}" if not is_before else messages['after_label']
    
    mode_row.append(Button.inline(
        before_text,
        data=f"HIST:IDX:{entry_index}:MODE:before"
    ))
    mode_row.append(Button.inline(
        after_text,
        data=f"HIST:IDX:{entry_index}:MODE:after"
    ))
    buttons.append(mode_row)
    
    nav_row = []
    if entry_index > 0:
        nav_row.append(Button.inline(
            f"← {messages['prev_label']}",
            data=f"HIST:IDX:{entry_index - 1}:MODE:{'before' if is_before else 'after'}"
        ))
    
    if entry_index < total_entries - 1:
        nav_row.append(Button.inline(
            f"{messages['next_label']} →",
            data=f"HIST:IDX:{entry_index + 1}:MODE:{'before' if is_before else 'after'}"
        ))
    
    if nav_row:
        buttons.append(nav_row)
    
    return buttons


def build_teacher_admin_keyboard(messages: dict) -> list:
    """
    Build inline keyboard for teacher admin panel.
    
    Args:
        messages: Localized messages dict
        
    Returns:
        List of button rows for Telethon
    """
    buttons = [
        [
            Button.inline(
                messages['admin_manage_channels'],
                data="ADMIN:MANAGE_CHANNELS"
            ),
        ],
        [
            Button.inline(
                messages['admin_add_style'],
                data="ADMIN:ADD_STYLE"
            ),
            Button.inline(
                messages['admin_list_styles'],
                data="ADMIN:LIST_STYLES"
            ),
        ]
    ]
    
    return buttons


def build_channel_management_keyboard(messages: dict) -> list:
    """
    Build inline keyboard for channel management.
    
    Args:
        messages: Localized messages dict
        
    Returns:
        List of button rows for Telethon
    """
    buttons = [
        [
            Button.inline(
                messages['admin_add_channel'],
                data="CHANNEL:ADD"
            ),
        ],
        [
            Button.inline(
                messages['admin_remove_channel'],
                data="CHANNEL:REMOVE"
            ),
            Button.inline(
                messages['admin_list_channels'],
                data="CHANNEL:LIST"
            ),
        ]
    ]
    
    return buttons


def build_channel_list_keyboard(channels: list[tuple[int, str]], messages: dict) -> list:
    """
    Build inline keyboard showing list of channels with remove buttons.
    
    Args:
        channels: List of (id, channel_ref) tuples
        messages: Localized messages dict
        
    Returns:
        List of button rows for Telethon
    """
    buttons = []
    
    for channel_id, channel_ref in channels:
        buttons.append([
            Button.inline(
                f"{channel_ref}",
                data=f"CHANNEL_INFO:{channel_id}"
            ),
            Button.inline(
                "❌",
                data=f"CHANNEL:REMOVE:{channel_id}"
            )
        ])
    
    return buttons
