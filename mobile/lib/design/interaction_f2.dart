import 'package:flutter/material.dart';

import 'behavior_primitives.dart';
import 'interaction_primitives.dart';
import 'makolo_theme.dart';

/// Selection is UI state, never membership or business authority.
class MakoloSelectionController extends ChangeNotifier {
  final Set<String> _selected = <String>{};
  Set<String> get selectedIds => Set.unmodifiable(_selected);
  int get count => _selected.length;
  bool contains(String id) => _selected.contains(id);

  void toggle(String id) {
    if (id.isEmpty) return;
    if (!_selected.add(id)) _selected.remove(id);
    notifyListeners();
  }

  void retainVisible(Iterable<String> visibleIds) {
    if (_selected.removeAllNotIn(visibleIds.toSet())) notifyListeners();
  }

  void clear() {
    if (_selected.isEmpty) return;
    _selected.clear();
    notifyListeners();
  }
}

extension _RetainIds on Set<String> {
  bool removeAllNotIn(Set<String> allowed) {
    final before = length;
    removeWhere((id) => !allowed.contains(id));
    return before != length;
  }
}

/// Opt-in local filtering. Only items explicitly supplied by an owner projection
/// are searchable; this never claims to search the global Makolo catalog.
List<T> makoloFilterLocal<T>(
  Iterable<T> items, {
  required String query,
  required String Function(T) textOf,
  String? category,
  String Function(T)? categoryOf,
}) {
  final needle = query.trim().toLowerCase();
  return List<T>.of(items)
      .where((item) {
        final textMatches =
            needle.isEmpty || textOf(item).toLowerCase().contains(needle);
        final categoryMatches =
            category == null ||
            category.isEmpty ||
            (categoryOf != null && categoryOf(item) == category);
        return textMatches && categoryMatches;
      })
      .toList(growable: false);
}

/// A shared bar, not a ranking engine. Caller chooses approved sort/filter
/// choices and stores/restores the current user view state.
class MakoloSortFilterBar extends StatefulWidget {
  const MakoloSortFilterBar({
    super.key,
    required this.query,
    required this.onQueryChanged,
    this.sortKey,
    this.sortOptions = const {},
    this.onSortChanged,
    this.filterKey,
    this.filterOptions = const {},
    this.onFilterChanged,
  });

  final String query;
  final ValueChanged<String> onQueryChanged;
  final String? sortKey;
  final Map<String, String> sortOptions;
  final ValueChanged<String?>? onSortChanged;
  final String? filterKey;
  final Map<String, String> filterOptions;
  final ValueChanged<String?>? onFilterChanged;

  @override
  State<MakoloSortFilterBar> createState() => _MakoloSortFilterBarState();
}

class _MakoloSortFilterBarState extends State<MakoloSortFilterBar> {
  late final TextEditingController _search;

  @override
  void initState() {
    super.initState();
    _search = TextEditingController(text: widget.query);
  }

  @override
  void didUpdateWidget(MakoloSortFilterBar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.query != _search.text) {
      _search.value = TextEditingValue(
        text: widget.query,
        selection: TextSelection.collapsed(offset: widget.query.length),
      );
    }
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: MakoloSpacing.compact,
      runSpacing: MakoloSpacing.sm,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 340, minWidth: 200),
          child: TextField(
            controller: _search,
            onChanged: widget.onQueryChanged,
            decoration: const InputDecoration(
              labelText: 'Chercher dans ces éléments',
              prefixIcon: Icon(Icons.search),
            ),
          ),
        ),
        if (widget.onSortChanged != null && widget.sortOptions.isNotEmpty)
          DropdownButton<String>(
            value: widget.sortOptions.containsKey(widget.sortKey)
                ? widget.sortKey
                : null,
            hint: const Text('Trier'),
            items: [
              for (final entry in widget.sortOptions.entries)
                DropdownMenuItem(value: entry.key, child: Text(entry.value)),
            ],
            onChanged: widget.onSortChanged,
          ),
        if (widget.onFilterChanged != null && widget.filterOptions.isNotEmpty)
          DropdownButton<String>(
            value: widget.filterOptions.containsKey(widget.filterKey)
                ? widget.filterKey
                : null,
            hint: const Text('Filtrer'),
            items: [
              for (final entry in widget.filterOptions.entries)
                DropdownMenuItem(value: entry.key, child: Text(entry.value)),
            ],
            onChanged: widget.onFilterChanged,
          ),
      ],
    );
  }
}

/// Reuse the existing safe-area bottom sheet rather than create a router.
class MakoloContextPreviewButton extends StatelessWidget {
  const MakoloContextPreviewButton({
    super.key,
    required this.builder,
    this.tooltip = 'Aperçu',
  });

  final WidgetBuilder builder;
  final String tooltip;

  @override
  Widget build(BuildContext context) => IconButton(
    tooltip: tooltip,
    icon: Icon(MakoloInteractionIcons.forIntent(MakoloActionIntent.inspect)),
    onPressed: () => showMakoloBottomSheet<void>(context, builder: builder),
  );
}

enum MakoloCommitOutcome { confirmed, rejected, conflict }

/// Authoritative reply. Confirmed requires an actual canonical value.
@immutable
class MakoloInlineSaveResult {
  const MakoloInlineSaveResult._(this.outcome, this.canonicalValue);
  const MakoloInlineSaveResult.confirmed(String value)
    : this._(MakoloCommitOutcome.confirmed, value);
  const MakoloInlineSaveResult.rejected()
    : this._(MakoloCommitOutcome.rejected, null);
  const MakoloInlineSaveResult.conflict()
    : this._(MakoloCommitOutcome.conflict, null);

  final MakoloCommitOutcome outcome;
  final String? canonicalValue;
}

/// Editing is local until the owner answers with its canonical saved value.
/// No optimistic success, automatic retry or generic endpoint.
class MakoloInlineEditor extends StatefulWidget {
  const MakoloInlineEditor({
    super.key,
    required this.value,
    required this.onSave,
    this.label = 'Modifier',
  });

  final String value;
  final String label;
  final Future<MakoloInlineSaveResult> Function(String value) onSave;

  @override
  State<MakoloInlineEditor> createState() => _MakoloInlineEditorState();
}

class _MakoloInlineEditorState extends State<MakoloInlineEditor> {
  late final TextEditingController _controller;
  bool _editing = false;
  bool _saving = false;
  String? _error;
  late String _confirmed;

  @override
  void initState() {
    super.initState();
    _confirmed = widget.value;
    _controller = TextEditingController(text: _confirmed);
  }

  @override
  void didUpdateWidget(MakoloInlineEditor oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.value != widget.value && !_saving) {
      _confirmed = widget.value;
      if (!_editing) _controller.text = _confirmed;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    final candidate = _controller.text;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final result = await widget.onSave(candidate);
      if (!mounted) return;
      setState(() {
        if (result.outcome == MakoloCommitOutcome.confirmed &&
            result.canonicalValue != null) {
          _confirmed = result.canonicalValue!;
          _controller.text = _confirmed;
          _editing = false;
        } else {
          _error = result.outcome == MakoloCommitOutcome.conflict
              ? 'Ce contenu a changé. Vérifiez la version actuelle.'
              : 'Modification non confirmée. Réessayez.';
        }
      });
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Modification non confirmée. Réessayez.');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_editing) {
      return Row(
        children: [
          Expanded(child: Text(_confirmed)),
          IconButton(
            tooltip: widget.label,
            onPressed: () => setState(() {
              _editing = true;
              _error = null;
            }),
            icon: const Icon(Icons.edit_outlined),
          ),
        ],
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: _controller,
          enabled: !_saving,
          decoration: InputDecoration(labelText: widget.label),
          onSubmitted: (_) => _save(),
        ),
        if (_error != null)
          Semantics(
            liveRegion: true,
            child: Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        Wrap(
          spacing: MakoloSpacing.sm,
          children: [
            TextButton(
              onPressed: _saving
                  ? null
                  : () => setState(() {
                      _controller.text = _confirmed;
                      _editing = false;
                      _error = null;
                    }),
              child: const Text('Annuler'),
            ),
            FilledButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Enregistrer'),
            ),
          ],
        ),
      ],
    );
  }
}

@immutable
class MakoloReorderEntry {
  const MakoloReorderEntry({
    required this.id,
    required this.label,
    required this.child,
  });

  final String id;
  final String label;
  final Widget child;
}

/// Drag handle plus accessible Up/Down. Parent alone supplies canonical order
/// after its owner returns true. There is no local authority or fake success.
class MakoloOwnerReorderList extends StatefulWidget {
  const MakoloOwnerReorderList({
    super.key,
    required this.entries,
    required this.onRequestReorder,
  });

  final List<MakoloReorderEntry> entries;
  final Future<bool> Function(List<String> proposedOrder) onRequestReorder;

  @override
  State<MakoloOwnerReorderList> createState() => _MakoloOwnerReorderListState();
}

class _MakoloOwnerReorderListState extends State<MakoloOwnerReorderList> {
  bool _busy = false;
  String? _error;

  Future<void> _propose(int from, int to) async {
    if (_busy ||
        from < 0 ||
        to < 0 ||
        from >= widget.entries.length ||
        to >= widget.entries.length ||
        from == to) {
      return;
    }
    final ids = widget.entries.map((entry) => entry.id).toList();
    final moved = ids.removeAt(from);
    ids.insert(to, moved);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final confirmed = await widget.onRequestReorder(List.unmodifiable(ids));
      if (!mounted) return;
      if (!confirmed) {
        setState(() => _error = 'Nouvel ordre non confirmé.');
      }
      // Caller must refresh authoritative order; do not rearrange entries here.
    } catch (_) {
      if (mounted) setState(() => _error = 'Nouvel ordre non confirmé.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    assert(
      widget.entries.map((entry) => entry.id).toSet().length ==
          widget.entries.length,
      'Reorder entries need unique IDs',
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (_error != null)
          Semantics(
            liveRegion: true,
            child: Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        ReorderableListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          buildDefaultDragHandles: false,
          itemCount: widget.entries.length,
          onReorderItem: (oldIndex, newIndex) {
            _propose(oldIndex, newIndex);
          },
          itemBuilder: (context, index) {
            final entry = widget.entries[index];
            return ListTile(
              key: ValueKey(entry.id),
              title: entry.child,
              leading: ReorderableDragStartListener(
                index: index,
                enabled: !_busy,
                child: Tooltip(
                  message: 'Réorganiser ${entry.label}',
                  child: const Icon(Icons.drag_indicator),
                ),
              ),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    tooltip: 'Monter ${entry.label}',
                    onPressed: _busy || index == 0
                        ? null
                        : () => _propose(index, index - 1),
                    icon: const Icon(Icons.keyboard_arrow_up),
                  ),
                  IconButton(
                    tooltip: 'Descendre ${entry.label}',
                    onPressed: _busy || index == widget.entries.length - 1
                        ? null
                        : () => _propose(index, index + 1),
                    icon: const Icon(Icons.keyboard_arrow_down),
                  ),
                ],
              ),
            );
          },
        ),
      ],
    );
  }
}

@immutable
class MakoloMoveDestination {
  const MakoloMoveDestination({required this.id, required this.label});
  final String id;
  final String label;
}

/// Destination list is pre-filtered by owner. On confirmed move only, close.
/// No implicit permission transfer to the destination.
class MakoloMoveDestinationButton extends StatelessWidget {
  const MakoloMoveDestinationButton({
    super.key,
    required this.destinations,
    required this.onRequestMove,
    this.label = 'Déplacer vers…',
  });

  final List<MakoloMoveDestination> destinations;
  final Future<bool> Function(String destinationId) onRequestMove;
  final String label;

  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
    onPressed: destinations.isEmpty
        ? null
        : () => showMakoloBottomSheet<void>(
            context,
            builder: (context) => _MakoloMoveSheet(
              destinations: destinations,
              onRequestMove: onRequestMove,
            ),
          ),
    icon: const Icon(Icons.drive_file_move_outline),
    label: Text(label),
  );
}

class _MakoloMoveSheet extends StatefulWidget {
  const _MakoloMoveSheet({
    required this.destinations,
    required this.onRequestMove,
  });

  final List<MakoloMoveDestination> destinations;
  final Future<bool> Function(String destinationId) onRequestMove;

  @override
  State<_MakoloMoveSheet> createState() => _MakoloMoveSheetState();
}

class _MakoloMoveSheetState extends State<_MakoloMoveSheet> {
  bool _busy = false;
  String? _error;

  Future<void> _move(String destinationId) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final confirmed = await widget.onRequestMove(destinationId);
      if (!mounted) return;
      if (confirmed) {
        Navigator.of(context).pop();
      } else {
        setState(() => _error = 'Déplacement non confirmé.');
      }
    } catch (_) {
      if (mounted) setState(() => _error = 'Déplacement non confirmé.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => SafeArea(
    child: Padding(
      padding: const EdgeInsets.all(MakoloSpacing.md),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Choisir une destination',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          if (_error != null)
            Semantics(
              liveRegion: true,
              child: Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          if (_busy) const LinearProgressIndicator(),
          ConstrainedBox(
            constraints: BoxConstraints(
              maxHeight: MediaQuery.sizeOf(context).height * 0.55,
            ),
            child: ListView(
              shrinkWrap: true,
              children: [
                for (final destination in widget.destinations)
                  ListTile(
                    enabled: !_busy,
                    title: Text(destination.label),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: _busy ? null : () => _move(destination.id),
                  ),
              ],
            ),
          ),
          TextButton(
            onPressed: _busy ? null : () => Navigator.of(context).pop(),
            child: const Text('Annuler'),
          ),
        ],
      ),
    ),
  );
}

/// Undo is only displayed if the owner truly exposes an inverse command.
/// The callback returns true only after the inverse has been confirmed.
class MakoloOwnerUndoButton extends StatefulWidget {
  const MakoloOwnerUndoButton({
    super.key,
    required this.available,
    required this.onRequestUndo,
    this.label = 'Annuler cette action',
  });

  final bool available;
  final Future<bool> Function() onRequestUndo;
  final String label;

  @override
  State<MakoloOwnerUndoButton> createState() => _MakoloOwnerUndoButtonState();
}

class _MakoloOwnerUndoButtonState extends State<MakoloOwnerUndoButton> {
  bool _busy = false;
  bool _confirmed = false;
  String? _error;

  Future<void> _undo() async {
    if (!widget.available || _busy || _confirmed) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final confirmed = await widget.onRequestUndo();
      if (!mounted) return;
      setState(() {
        _confirmed = confirmed;
        if (!confirmed) _error = 'Annulation non confirmée.';
      });
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Annulation non confirmée.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.available || _confirmed) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        OutlinedButton.icon(
          onPressed: _busy ? null : _undo,
          icon: _busy
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.undo),
          label: Text(widget.label),
        ),
        if (_error != null)
          Semantics(
            liveRegion: true,
            child: Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
      ],
    );
  }
}

/// Long-press shortcut and a permanently visible accessible menu invoke the
/// exact same owner-provided actions. Never make long-press the only route.
class MakoloContextActionRow extends StatelessWidget {
  const MakoloContextActionRow({
    super.key,
    required this.child,
    required this.actions,
    required this.onSelected,
  });

  final Widget child;
  final List<MakoloInteractionAction> actions;
  final ValueChanged<MakoloInteractionAction> onSelected;

  Future<void> _showActions(BuildContext context) async {
    if (actions.isEmpty) return;
    await showMakoloBottomSheet<void>(
      context,
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.compact),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Actions',
                style: Theme.of(sheetContext).textTheme.titleLarge,
              ),
              ConstrainedBox(
                constraints: BoxConstraints(
                  maxHeight: MediaQuery.sizeOf(sheetContext).height * 0.6,
                ),
                child: ListView(
                  shrinkWrap: true,
                  children: [
                    for (final action in actions)
                      ListTile(
                        enabled: action.enabled,
                        leading: Icon(
                          MakoloInteractionIcons.forIntent(action.intent),
                          color: action.destructive
                              ? Theme.of(sheetContext).colorScheme.error
                              : null,
                        ),
                        title: Text(action.label),
                        onTap: action.enabled
                            ? () {
                                Navigator.of(sheetContext).pop();
                                onSelected(action);
                              }
                            : null,
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(
        child: GestureDetector(
          behavior: HitTestBehavior.translucent,
          onLongPress: actions.isEmpty ? null : () => _showActions(context),
          child: child,
        ),
      ),
      if (actions.isNotEmpty)
        MakoloActionMenu(actions: actions, onSelected: onSelected),
    ],
  );
}
