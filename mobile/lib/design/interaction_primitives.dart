import 'package:flutter/material.dart';

import 'makolo_theme.dart';

/// UI intent only. Owner services resolve permissions and command consequences.
enum MakoloActionIntent {
  open,
  inspect,
  more,
  select,
  sort,
  filter,
  reorder,
  move,
  link,
  unlink,
  transition,
  edit,
  bulk,
  undo,
  search,
}

abstract final class MakoloInteractionIcons {
  static IconData forIntent(MakoloActionIntent intent) => switch (intent) {
    MakoloActionIntent.open => Icons.open_in_new_outlined,
    MakoloActionIntent.inspect => Icons.view_sidebar_outlined,
    MakoloActionIntent.more => Icons.more_horiz,
    MakoloActionIntent.select => Icons.check_box_outlined,
    MakoloActionIntent.sort => Icons.sort,
    MakoloActionIntent.filter => Icons.filter_alt_outlined,
    MakoloActionIntent.reorder => Icons.drag_indicator,
    MakoloActionIntent.move => Icons.drive_file_move_outline,
    MakoloActionIntent.link => Icons.link,
    MakoloActionIntent.unlink => Icons.link_off,
    MakoloActionIntent.transition => Icons.sync_alt,
    MakoloActionIntent.edit => Icons.edit_outlined,
    MakoloActionIntent.bulk => Icons.library_add_check_outlined,
    MakoloActionIntent.undo => Icons.undo,
    MakoloActionIntent.search => Icons.search,
  };
}

/// Display-only action. It does not grant authority or own any domain state.
@immutable
class MakoloInteractionAction {
  const MakoloInteractionAction({
    required this.id,
    required this.label,
    required this.intent,
    this.enabled = true,
    this.destructive = false,
  });

  final String id;
  final String label;
  final MakoloActionIntent intent;
  final bool enabled;
  final bool destructive;
}

/// Shared context menu. Selected intents must still be revalidated by owner.
class MakoloActionMenu extends StatelessWidget {
  const MakoloActionMenu({
    super.key,
    required this.actions,
    required this.onSelected,
    this.tooltip = 'Actions',
    this.icon = Icons.more_horiz,
  });

  final List<MakoloInteractionAction> actions;
  final ValueChanged<MakoloInteractionAction> onSelected;
  final String tooltip;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    if (actions.isEmpty) return const SizedBox.shrink();
    final theme = Theme.of(context);
    return PopupMenuButton<String>(
      tooltip: tooltip,
      icon: Icon(icon),
      iconSize: 22,
      constraints: const BoxConstraints(minWidth: 200, maxWidth: 320),
      position: PopupMenuPosition.under,
      onSelected: (id) {
        for (final action in actions) {
          if (action.id == id && action.enabled) {
            onSelected(action);
            return;
          }
        }
      },
      itemBuilder: (context) => [
        for (final action in actions)
          PopupMenuItem<String>(
            value: action.id,
            enabled: action.enabled,
            child: Row(
              children: [
                Icon(
                  MakoloInteractionIcons.forIntent(action.intent),
                  size: 20,
                  color: action.destructive
                      ? theme.colorScheme.error
                      : theme.colorScheme.onSurface,
                ),
                const SizedBox(width: MakoloSpacing.compact),
                Flexible(
                  child: Text(
                    action.label,
                    style: TextStyle(
                      color: action.destructive
                          ? theme.colorScheme.error
                          : theme.colorScheme.onSurface,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

/// Selection presentation; no batch mutation transport or permissions.
class MakoloSelectionBar extends StatelessWidget {
  const MakoloSelectionBar({
    super.key,
    required this.count,
    required this.onClear,
    this.actions = const [],
    this.onSelected,
  });

  final int count;
  final VoidCallback onClear;
  final List<MakoloInteractionAction> actions;
  final ValueChanged<MakoloInteractionAction>? onSelected;

  @override
  Widget build(BuildContext context) {
    if (count <= 0) return const SizedBox.shrink();
    final theme = Theme.of(context);
    final countLabel = '$count sélectionné${count > 1 ? 's' : ''}';
    return Semantics(
      container: true,
      label: '$count élément${count > 1 ? 's sélectionnés' : ' sélectionné'}',
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(MakoloRadii.card),
          border: Border.all(color: theme.colorScheme.outlineVariant),
          color: theme.colorScheme.surface,
        ),
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.compact),
          child: Row(
            children: [
              Expanded(child: Text(countLabel)),
              if (actions.isNotEmpty && onSelected != null)
                MakoloActionMenu(
                  actions: actions,
                  onSelected: onSelected!,
                  tooltip: 'Actions sur la sélection',
                ),
              TextButton(onPressed: onClear, child: const Text('Terminer')),
            ],
          ),
        ),
      ),
    );
  }
}
