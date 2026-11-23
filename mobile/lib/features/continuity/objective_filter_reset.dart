import 'package:flutter/material.dart';

/// Shared F2 filter action for canonical Project and Dossier lists.
///
/// Filters are local presentation state; this button never changes owner data.
class ObjectiveFilterReset extends StatelessWidget {
  const ObjectiveFilterReset({
    super.key,
    required this.active,
    required this.onClear,
  });

  final bool active;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    if (!active) return const SizedBox.shrink();
    return TextButton.icon(
      key: const ValueKey<String>('objective-filters-clear'),
      onPressed: onClear,
      icon: const Icon(Icons.filter_alt_off_outlined, size: 18),
      label: const Text('Tout effacer'),
    );
  }
}
