import 'package:flutter/material.dart';

import 'objective_organizer_data.dart';

/// Compact, accessible mode control. Creation actions stay outside this
/// secondary group and remain available in the non-scrolling app bar.
class OrganizerViewSwitcher extends StatelessWidget {
  const OrganizerViewSwitcher({
    super.key,
    required this.selected,
    required this.onSelected,
  });

  final OrganizerMode selected;
  final ValueChanged<OrganizerMode> onSelected;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      key: const Key('organizer-view-toggle'),
      decoration: BoxDecoration(
        border: Border.all(color: scheme.outlineVariant),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _mode(
            context,
            OrganizerMode.cards,
            Icons.grid_view_rounded,
            'Cartes',
          ),
          _mode(context, OrganizerMode.list, Icons.view_list_rounded, 'Liste'),
          _mode(
            context,
            OrganizerMode.explorer,
            Icons.account_tree_rounded,
            'Explorateur',
          ),
        ],
      ),
    );
  }

  Widget _mode(
    BuildContext context,
    OrganizerMode mode,
    IconData icon,
    String label,
  ) {
    final isSelected = mode == selected;
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      selected: isSelected,
      child: IconButton(
        key: Key('organizer-view-${mode.name}'),
        tooltip: 'Vue $label',
        onPressed: () => onSelected(mode),
        icon: Icon(icon, size: 19),
        color: isSelected ? scheme.onPrimaryContainer : scheme.onSurfaceVariant,
        style: IconButton.styleFrom(
          fixedSize: const Size(44, 44),
          padding: EdgeInsets.zero,
          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
          backgroundColor: isSelected
              ? scheme.primaryContainer
              : Colors.transparent,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      ),
    );
  }
}
