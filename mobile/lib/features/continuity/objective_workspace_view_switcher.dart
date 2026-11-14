import 'package:flutter/material.dart';

/// Shared, icon-only view control for Project and Dossier in every actor context.
/// The readable names remain available to accessibility and long-press tooltip.
class ObjectiveViewOption<T> {
  const ObjectiveViewOption(this.value, this.icon, this.label);

  final T value;
  final IconData icon;
  final String label;
}

class ObjectiveWorkspaceViewSwitcher<T> extends StatelessWidget {
  const ObjectiveWorkspaceViewSwitcher({
    super.key,
    required this.selected,
    required this.options,
    required this.onSelected,
    this.compact = false,
  });

  final T selected;
  final List<ObjectiveViewOption<T>> options;
  final ValueChanged<T> onSelected;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Align(
      alignment: AlignmentDirectional.centerStart,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: options.length * (compact ? 44.0 : 56.0)),
        child: Container(
          decoration: BoxDecoration(
            border: Border.all(color: scheme.outlineVariant),
            borderRadius: BorderRadius.circular(compact ? 10 : 12),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final option in options)
                Expanded(
                  child: Semantics(
                    button: true,
                    selected: selected == option.value,
                    child: IconButton(
                      tooltip: option.label,
                      onPressed: () => onSelected(option.value),
                      icon: Icon(option.icon, size: 20),
                      color: selected == option.value
                          ? scheme.onPrimaryContainer
                          : scheme.onSurfaceVariant,
                      style: IconButton.styleFrom(
                        fixedSize: Size(compact ? 42 : 48, 44),
                        padding: EdgeInsets.zero,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        backgroundColor: selected == option.value
                            ? scheme.primaryContainer
                            : Colors.transparent,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
