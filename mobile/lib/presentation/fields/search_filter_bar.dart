import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';

/// Shared Discovery search field and modal filter panel for guest and Profile.
/// Owners retain query state and own all data acquisition and permissions.
class SearchFilterBar extends StatelessWidget {
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

  Future<void> _openFilters(BuildContext context) async {
    FocusManager.instance.primaryFocus?.unfocus();
    onExpansionChanged?.call(true);
    try {
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        showDragHandle: true,
        backgroundColor: Theme.of(context).colorScheme.surface,
        builder: (sheetContext) {
          final colors = Theme.of(sheetContext).colorScheme;
          return Padding(
            padding: EdgeInsets.only(
              bottom: MediaQuery.viewInsetsOf(sheetContext).bottom,
            ),
            child: FractionallySizedBox(
              heightFactor: 0.85,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: MakoloSpacing.lg,
                      vertical: MakoloSpacing.sm,
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(
                            'Affiner la recherche',
                            style: Theme.of(sheetContext).textTheme.titleLarge,
                          ),
                        ),
                        IconButton(
                          tooltip: 'Fermer les filtres',
                          onPressed: () => Navigator.of(sheetContext).pop(),
                          icon: const Icon(Icons.close_rounded),
                        ),
                      ],
                    ),
                  ),
                  Expanded(
                    child: SingleChildScrollView(
                      key: const Key('discovery-filter-sheet-scroll'),
                      keyboardDismissBehavior:
                          ScrollViewKeyboardDismissBehavior.onDrag,
                      padding: const EdgeInsets.symmetric(
                        horizontal: MakoloSpacing.lg,
                        vertical: MakoloSpacing.sm,
                      ),
                      child: Card(
                        key: filterPanelKey,
                        margin: EdgeInsets.zero,
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius:
                              BorderRadius.circular(MakoloRadii.card),
                          side: BorderSide(color: colors.outlineVariant),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(MakoloSpacing.md),
                          child: filters,
                        ),
                      ),
                    ),
                  ),
                  if (showResultsAction || onClearFilters != null)
                    SafeArea(
                      top: false,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(
                          MakoloSpacing.lg,
                          MakoloSpacing.sm,
                          MakoloSpacing.lg,
                          MakoloSpacing.md,
                        ),
                        child: Row(
                          children: [
                            if (onClearFilters != null)
                              Expanded(
                                child: TextButton(
                                  key: const Key('discovery-clear-filters'),
                                  onPressed: () {
                                    onClearFilters!();
                                    Navigator.of(sheetContext).pop();
                                  },
                                  child: const Text('Effacer les filtres'),
                                ),
                              ),
                            if (showResultsAction) ...[
                              const SizedBox(width: MakoloSpacing.sm),
                              Expanded(
                                flex: 2,
                                child: FilledButton(
                                  key: const Key('discovery-show-results'),
                                  onPressed: () {
                                    FocusManager.instance.primaryFocus
                                        ?.unfocus();
                                    Navigator.of(sheetContext).pop();
                                  },
                                  child: const Text('Voir les résultats'),
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            ),
          );
        },
      );
    } finally {
      onExpansionChanged?.call(false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(child: searchField),
        const SizedBox(width: MakoloSpacing.sm),
        SizedBox(
          width: 56,
          height: 56,
          child: IconButton(
            key: filterButtonKey,
            tooltip: 'Afficher les filtres',
            onPressed: () => _openFilters(context),
            icon: const Icon(Icons.tune_rounded),
            style: IconButton.styleFrom(
              backgroundColor: hasActiveFilters
                  ? colors.primaryContainer
                  : colors.surface,
              foregroundColor: hasActiveFilters
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
    );
  }
}
