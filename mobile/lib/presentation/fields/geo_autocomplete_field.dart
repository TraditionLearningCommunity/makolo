import 'package:flutter/material.dart';

import '../../platform/location/geo_search_gateway.dart';
import '../search/progressive_search_coordinator.dart';

/// Autocomplete for worldwide places. It does not persist Makolo Geography.
/// With no configured provider, the field remains a usable free-text input.
class GeoAutocompleteField extends StatefulWidget {
  const GeoAutocompleteField({
    super.key,
    required this.controller,
    this.gateway,
    this.fieldKey,
    this.labelText = 'Où ?',
    this.hintText = 'Ville ou lieu',
    this.onSelected,
    this.onEdited,
    this.onSubmitted,
    this.debounce = const Duration(milliseconds: 350),
  });

  final TextEditingController controller;
  final GeoSearchGateway? gateway;
  final Key? fieldKey;
  final String labelText;
  final String hintText;
  final ValueChanged<GeoSuggestion>? onSelected;
  final VoidCallback? onEdited;
  final VoidCallback? onSubmitted;
  final Duration debounce;

  @override
  State<GeoAutocompleteField> createState() => _GeoAutocompleteFieldState();
}

class _GeoAutocompleteFieldState extends State<GeoAutocompleteField> {
  late final ProgressiveSearchCoordinator _coordinator;
  final _suggestionsAnchor = GlobalKey();
  GeoSearchCancellation? _pending;
  bool _loading = false;
  bool _showSuggestions = false;
  bool _unavailable = false;
  bool _searched = false;
  List<GeoSuggestion> _suggestions = const [];

  @override
  void initState() {
    super.initState();
    _coordinator = ProgressiveSearchCoordinator(
      onSearch: (revision) => _suggest(widget.controller.text.trim(), revision),
      debounce: widget.debounce,
    );
    widget.controller.addListener(_handleControllerClear);
  }

  @override
  void didUpdateWidget(covariant GeoAutocompleteField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_handleControllerClear);
      widget.controller.addListener(_handleControllerClear);
      _invalidate();
      _suggestions = const [];
      _showSuggestions = false;
    }
    if (oldWidget.gateway != widget.gateway) {
      _invalidate();
      _suggestions = const [];
      _showSuggestions = false;
    }
  }

  // Programmatic filter resets do not call TextField.onChanged. Cancel any
  // open suggestions when the owner clears the shared controller.
  void _handleControllerClear() {
    if (widget.controller.text.trim().isNotEmpty) return;
    if (!_showSuggestions && !_loading && _suggestions.isEmpty && !_unavailable) {
      return;
    }
    _invalidate();
    if (!mounted) return;
    setState(() {
      _suggestions = const [];
      _showSuggestions = false;
      _loading = false;
      _unavailable = false;
      _searched = false;
    });
  }

  void _invalidate() {
    _coordinator.invalidate();
    _pending?.cancel();
    _pending = null;
  }

  @override
  void dispose() {
    widget.controller.removeListener(_handleControllerClear);
    _pending?.cancel();
    _coordinator.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    widget.onEdited?.call();
    _invalidate();
    final query = value.trim();
    setState(() {
      _suggestions = const [];
      _loading = false;
      _unavailable = false;
      _searched = false;
      _showSuggestions = widget.gateway != null && query.isNotEmpty;
    });
    if (widget.gateway == null || query.isEmpty) return;
    _coordinator.changed();
  }

  Future<void> _suggest(String query, int revision) async {
    final gateway = widget.gateway;
    if (gateway == null || !mounted || !_coordinator.isCurrent(revision)) {
      return;
    }
    final cancel = GeoSearchCancellation();
    _pending = cancel;
    setState(() => _loading = true);
    try {
      final results = await gateway.suggest(
        query,
        limit: 5,
        cancelToken: cancel,
      );
      if (!mounted || !_coordinator.isCurrent(revision) || cancel.isCancelled) {
        return;
      }
      setState(() {
        _loading = false;
        _suggestions = results;
        _unavailable = false;
        _searched = true;
      });
      if (results.isNotEmpty) _revealSuggestions();
    } on Object {
      if (!mounted || !_coordinator.isCurrent(revision) || cancel.isCancelled) {
        return;
      }
      setState(() {
        _loading = false;
        _suggestions = const [];
        _unavailable = true;
      });
    } finally {
      if (identical(_pending, cancel)) _pending = null;
    }
  }

  void _revealSuggestions() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_showSuggestions || _suggestions.isEmpty) return;
      final target = _suggestionsAnchor.currentContext;
      if (target == null) return;
      // Keep provider suggestions reachable when the keyboard shrinks the
      // filter panel. This scrolls the existing parents, not a new overlay.
      Scrollable.ensureVisible(
        target,
        duration: const Duration(milliseconds: 180),
        alignment: 0.2,
        curve: Curves.easeOut,
      );
    });
  }

  void _choose(GeoSuggestion suggestion) {
    _invalidate();
    widget.controller
      ..text = suggestion.label
      ..selection = TextSelection.collapsed(offset: suggestion.label.length);
    setState(() {
      _suggestions = const [];
      _showSuggestions = false;
      _loading = false;
      _unavailable = false;
      _searched = false;
    });
    FocusScope.of(context).unfocus();
    widget.onSelected?.call(suggestion);
  }

  void _clear() {
    widget.controller.clear();
    _onChanged('');
  }

  void _submit() {
    _invalidate();
    setState(() {
      _showSuggestions = false;
      _loading = false;
    });
    widget.onSubmitted?.call();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          key: widget.fieldKey,
          controller: widget.controller,
          onChanged: _onChanged,
          onSubmitted: (_) => _submit(),
          textInputAction: TextInputAction.search,
          decoration: InputDecoration(
            labelText: widget.labelText,
            hintText: widget.hintText,
            prefixIcon: const Icon(Icons.place_outlined),
            suffixIcon: _loading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: Center(
                      child: SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
                  )
                : widget.controller.text.isEmpty
                ? null
                : IconButton(
                    key: const Key('geo-search-clear'),
                    tooltip: 'Effacer le lieu',
                    onPressed: _clear,
                    icon: const Icon(Icons.close_rounded),
                  ),
            border: const OutlineInputBorder(),
          ),
        ),
        if (widget.gateway == null && widget.controller.text.trim().isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              'Suggestions géographiques non configurées. La saisie libre reste possible.',
              key: const Key('geo-suggestions-unconfigured'),
              style: theme.textTheme.bodySmall?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
          ),
        if (_showSuggestions && _unavailable)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              'Suggestions indisponibles. Vous pouvez saisir le lieu.',
              key: const Key('geo-suggestions-error'),
              style: theme.textTheme.bodySmall?.copyWith(color: colors.error),
            ),
          ),
        if (_showSuggestions &&
            _searched &&
            !_loading &&
            !_unavailable &&
            _suggestions.isEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Text(
              'Aucun lieu trouvé. Vous pouvez saisir le lieu manuellement.',
              key: Key('geo-suggestions-empty'),
            ),
          ),
        if (_showSuggestions && _suggestions.isNotEmpty)
          Card(
            key: const Key('geo-suggestions'),
            margin: const EdgeInsets.only(top: 4),
            clipBehavior: Clip.antiAlias,
            child: ConstrainedBox(
              key: _suggestionsAnchor,
              constraints: const BoxConstraints(maxHeight: 192),
              child: ListView(
                shrinkWrap: true,
                padding: EdgeInsets.zero,
                children: [
                  for (final suggestion in _suggestions)
                    ListTile(
                      dense: true,
                      leading: const Icon(Icons.location_on_outlined),
                      title: Text(suggestion.label, maxLines: 2),
                      onTap: () => _choose(suggestion),
                    ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
