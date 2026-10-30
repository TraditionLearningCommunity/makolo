import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';

/// Shared compact search + contextual filter disclosure.
/// The domain owns the search field and the filter criteria.
class SearchFilterBar extends StatefulWidget {
  const SearchFilterBar({
    super.key,
    required this.searchField,
    required this.filters,
    required this.filterButtonKey,
    required this.filterPanelKey,
    this.hasActiveFilters = false,
    this.onExpansionChanged,
    this.onClearFilters,
    this.showResultsAction = false,
  });

  final Widget searchField;
  final Widget filters;
  final Key filterButtonKey;
  final Key filterPanelKey;
  final bool hasActiveFilters;
  final ValueChanged<bool>? onExpansionChanged;
  final VoidCallback? onClearFilters;
  final bool showResultsAction;

  @override
  State<SearchFilterBar> createState() => _SearchFilterBarState();
}

class _SearchFilterBarState extends State<SearchFilterBar> {
  bool _expanded = false;

  void _setExpanded(bool value) {
    if (_expanded == value) return;
    setState(() => _expanded = value);
    widget.onExpansionChanged?.call(value);
  }

  void _showResults() {
    FocusManager.instance.primaryFocus?.unfocus();
    _setExpanded(false);
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(child: widget.searchField),
            const SizedBox(width: MakoloSpacing.sm),
            SizedBox(
              width: 56,
              height: 56,
              child: IconButton(
                key: widget.filterButtonKey,
                tooltip: _expanded
                    ? 'Masquer les filtres'
                    : 'Afficher les filtres',
                isSelected: _expanded,
                onPressed: () => _setExpanded(!_expanded),
                icon: const Icon(Icons.tune_rounded),
                selectedIcon: const Icon(Icons.close_rounded),
                style: IconButton.styleFrom(
                  backgroundColor: _expanded || widget.hasActiveFilters
                      ? colors.primaryContainer
                      : colors.surface,
                  foregroundColor: _expanded || widget.hasActiveFilters
                      ? colors.onPrimaryContainer
                      : colors.onSurfaceVariant,
                  side: BorderSide(color: colors.outlineVariant),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(MakoloRadii.card),
                  ),
                ),
              ),
            ),
          ],
        ),
        if (_expanded) ...[
          const SizedBox(height: MakoloSpacing.md),
          Card(
            key: widget.filterPanelKey,
            margin: EdgeInsets.zero,
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(MakoloRadii.card),
              side: BorderSide(color: colors.outlineVariant),
            ),
            child: Padding(
              padding: const EdgeInsets.all(MakoloSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                mainAxisSize: MainAxisSize.min,
                children: [
                  widget.filters,
                  if (widget.onClearFilters != null || widget.showResultsAction) ...[
                    const SizedBox(height: MakoloSpacing.md),
                    Wrap(
                      alignment: WrapAlignment.end,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      spacing: MakoloSpacing.sm,
                      children: [
                        if (widget.onClearFilters != null)
                          TextButton(
                            key: const Key('discovery-clear-filters'),
                            onPressed: widget.onClearFilters,
                            child: const Text('Effacer les filtres'),
                          ),
                        if (widget.showResultsAction)
                          FilledButton(
                            key: const Key('discovery-show-results'),
                            onPressed: _showResults,
                            child: const Text('Voir les résultats'),
                          ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }
}
