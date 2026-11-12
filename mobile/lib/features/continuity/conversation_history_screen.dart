import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../network/api_error.dart';
import 'conversation_repository.dart';

List<Map<String, dynamic>> _pointRows(Object? raw) {
  if (raw is! List) return const [];
  return [
    for (final item in raw)
      if (item is Map)
        item.map((key, value) => MapEntry(key.toString(), value)),
  ];
}

/// A read-only N2 depth of canonical Points, not a second messaging timeline.
/// Every remote continuation is signed and audience-checked by the owner.
class ConversationHistoryScreen extends StatefulWidget {
  const ConversationHistoryScreen({
    super.key,
    required this.repository,
    required this.conversationId,
    required this.onOpenPoint,
    this.initialQuery = '',
    this.initialSection = 'history',
  });

  final ConversationRepository repository;
  final String conversationId;
  final ValueChanged<String> onOpenPoint;
  final String initialQuery;
  final String initialSection;

  @override
  State<ConversationHistoryScreen> createState() =>
      _ConversationHistoryScreenState();
}

class _ConversationHistoryScreenState extends State<ConversationHistoryScreen> {
  final _queryController = TextEditingController();
  final _scrollController = ScrollController();
  final List<Map<String, dynamic>> _rows = [];
  Timer? _searchDebounce;
  String _query = '';
  String _section = 'history';
  String? _nextCursor;
  String? _error;
  bool _loading = false;
  bool _initialAttempted = false;
  bool _showingLocal = false;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    _section = {'history', 'all', 'active'}.contains(widget.initialSection)
        ? widget.initialSection
        : 'history';
    _query = widget.initialQuery.trim();
    _queryController.text = _query;
    unawaited(_prepare());
  }

  @override
  void didUpdateWidget(covariant ConversationHistoryScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.repository != oldWidget.repository ||
        widget.conversationId != oldWidget.conversationId) {
      _generation++;
      _rows.clear();
      _nextCursor = null;
      _error = null;
      _initialAttempted = false;
      _showingLocal = false;
      _section = widget.initialSection;
      _query = widget.initialQuery.trim();
      _queryController.text = _query;
      unawaited(_prepare());
    }
  }

  @override
  void dispose() {
    _generation++;
    _searchDebounce?.cancel();
    _queryController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _prepare() async {
    if (_query.isEmpty && _section == 'history') {
      try {
        final source = await widget.repository.readDetailSource(
          widget.conversationId,
        );
        if (source.lastErrorCode == 'permission_denied' ||
            source.lastErrorCode == 'not_found') {
          if (mounted) {
            setState(() {
              _error = 'Cette conversation n’est plus accessible.';
              _initialAttempted = true;
            });
          }
          return;
        }
        final cached = await widget.repository.readPointDepth(
          widget.conversationId,
        );
        if (cached != null &&
            mounted &&
            _query.isEmpty &&
            _section == 'history') {
          setState(() {
            _rows
              ..clear()
              ..addAll(_pointRows(cached.payload['results']).reversed);
            _nextCursor = cached.payload['next_cursor']?.toString();
            _showingLocal = true;
          });
        }
      } on Object {
        // The owner's network check will establish the visible final state.
      }
    }
    if (mounted) unawaited(_load(reset: true));
  }

  Future<void> _load({bool reset = false}) async {
    if (_loading) return;
    final generation = ++_generation;
    final priorQuery = _query;
    final priorSection = _section;
    final cursor = reset ? null : _nextCursor;
    final previousExtent = _scrollController.hasClients
        ? _scrollController.position.maxScrollExtent
        : 0.0;
    final previousOffset = _scrollController.hasClients
        ? _scrollController.offset
        : 0.0;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final payload = await widget.repository.pointDepth(
        conversationId: widget.conversationId,
        query: priorQuery,
        section: priorSection,
        cursor: cursor,
      );
      if (!mounted ||
          generation != _generation ||
          widget.conversationId.isEmpty ||
          _query != priorQuery ||
          _section != priorSection) {
        return;
      }
      // C5 returns newest-first to advance the signed keyset cursor.
      // Every page is displayed oldest-first, with older pages prepended.
      final arrived = _pointRows(payload['results']).reversed.toList();
      setState(() {
        if (reset) _rows.clear();
        final known = _rows.map((row) => row['id']?.toString()).toSet();
        final fresh = <Map<String, dynamic>>[];
        for (final row in arrived) {
          if (known.add(row['id']?.toString())) fresh.add(row);
        }
        if (reset) {
          _rows.addAll(fresh);
        } else {
          _rows.insertAll(0, fresh);
        }
        _nextCursor = payload['next_cursor']?.toString();
        _showingLocal = false;
        _initialAttempted = true;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted ||
            generation != _generation ||
            !_scrollController.hasClients) {
          return;
        }
        if (reset) {
          _scrollController.jumpTo(0);
        } else {
          final delta =
              _scrollController.position.maxScrollExtent - previousExtent;
          _scrollController.jumpTo(
            (previousOffset + delta)
                .clamp(
                  _scrollController.position.minScrollExtent,
                  _scrollController.position.maxScrollExtent,
                )
                .toDouble(),
          );
        }
      });
    } on MakoloApiError catch (error) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _initialAttempted = true;
        if (error.statusCode == 403 || error.statusCode == 404) {
          _rows.clear();
          _nextCursor = null;
          _showingLocal = false;
          _error = 'Cette conversation n’est plus accessible.';
        } else if (error.statusCode == 400 && cursor != null) {
          _nextCursor = null;
          _error = 'Résultats modifiés. Relancez la recherche.';
        } else {
          _error = _rows.isNotEmpty
              ? 'Actualisation indisponible. La dernière lecture est conservée.'
              : 'Impossible de charger les Points.';
        }
      });
    } on Object {
      if (!mounted || generation != _generation) return;
      setState(() {
        _initialAttempted = true;
        _error = _rows.isNotEmpty
            ? 'Hors ligne · dernière lecture disponible.'
            : 'Connexion nécessaire pour retrouver les Points.';
      });
    } finally {
      if (mounted && generation == _generation) {
        setState(() => _loading = false);
      }
    }
  }

  void _scheduleQuery(String value) {
    _searchDebounce?.cancel();
    final term = value.trim();
    if (term == _query) return;
    _generation++;
    setState(() {
      _query = term;
      if (term.isNotEmpty && _section == 'history') {
        _section = 'all';
      }
      _nextCursor = null;
      _rows.clear();
      _showingLocal = false;
      _error = null;
      _loading = false;
    });
    _searchDebounce = Timer(const Duration(milliseconds: 320), () {
      if (mounted) unawaited(_load(reset: true));
    });
  }

  void _setSection(String value) {
    if (value == _section) return;
    _searchDebounce?.cancel();
    _generation++;
    setState(() {
      _section = value;
      _nextCursor = null;
      _rows.clear();
      _showingLocal = false;
      _error = null;
      _loading = false;
    });
    unawaited(_load(reset: true));
  }

  List<Widget> _chronologicalHistory(BuildContext context) {
    final widgets = <Widget>[];
    DateTime? previousDay;
    DateTime? publishedDate(Map<String, dynamic> row) => DateTime.tryParse(
      row['published_at']?.toString() ?? row['updated_at']?.toString() ?? '',
    )?.toLocal();

    var index = 0;
    while (index < _rows.length) {
      final row = _rows[index];
      final day = publishedDate(row);
      if (day != null &&
          (previousDay == null || !DateUtils.isSameDay(previousDay, day))) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Center(
              child: Text(
                MaterialLocalizations.of(context).formatMediumDate(day),
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ),
          ),
        );
        previousDay = day;
      }
      if (row['timeline_compact'] == true) {
        var next = index + 1;
        while (next < _rows.length &&
            _rows[next]['timeline_compact'] == true &&
            DateUtils.isSameDay(day, publishedDate(_rows[next]))) {
          next++;
        }
        final group = _rows.sublist(index, next);
        widgets.add(
          _HistoricalCompletedGroup(
            key: PageStorageKey<String>(
              'history-completed-${group.first['id']}-${group.last['id']}',
            ),
            rows: group,
            onOpenPoint: widget.onOpenPoint,
          ),
        );
        index = next;
      } else {
        final id = row['id']?.toString() ?? '';
        widgets.add(
          _HistoricalPointRow(
            key: ValueKey('history-row-$id'),
            row: row,
            onOpenRelated: widget.onOpenPoint,
            onOpen: () {
              if (id.isNotEmpty) widget.onOpenPoint(id);
            },
          ),
        );
        index++;
      }
    }
    return widgets;
  }

  @override
  Widget build(BuildContext context) {
    final themed = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Retrouver un Point'),
        actions: [
          MakoloIconActionButton(
            tooltip: 'Actualiser',
            onPressed: _loading ? null : () => _load(reset: true),
            icon: Icons.refresh_rounded,
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 780),
            child: ListView(
              key: PageStorageKey<String>(
                'conversation-history-${widget.conversationId}',
              ),
              controller: _scrollController,
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 36),
              children: [
                TextField(
                  key: const Key('conversation-history-search'),
                  controller: _queryController,
                  onChanged: _scheduleQuery,
                  maxLength: 120,
                  textInputAction: TextInputAction.search,
                  decoration: const InputDecoration(
                    labelText: 'Rechercher',
                    hintText: 'Point, décision, fichier…',
                    prefixIcon: Icon(Icons.search_rounded),
                    border: OutlineInputBorder(),
                    counterText: '',
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    ChoiceChip(
                      key: const Key('conversation-history-history'),
                      label: const Text('Historique'),
                      selected: _section == 'history',
                      onSelected: (_) => _setSection('history'),
                    ),
                    ChoiceChip(
                      key: const Key('conversation-history-all'),
                      label: const Text('Tous les Points'),
                      selected: _section == 'all',
                      onSelected: (_) => _setSection('all'),
                    ),
                    ChoiceChip(
                      key: const Key('conversation-history-active'),
                      label: const Text('En cours'),
                      selected: _section == 'active',
                      onSelected: (_) => _setSection('active'),
                    ),
                  ],
                ),
                if (_showingLocal)
                  const Padding(
                    padding: EdgeInsets.only(top: 12),
                    child: Text(
                      'Dernière lecture sur cet appareil · vérification en cours',
                    ),
                  ),
                if (_error != null) ...[
                  const SizedBox(height: 14),
                  Semantics(
                    liveRegion: true,
                    child: Text(
                      _error!,
                      key: const Key('conversation-history-error'),
                      style: themed.textTheme.bodySmall,
                    ),
                  ),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: MakoloActionButton(
                      label: 'Réessayer',
                      onPressed: _loading ? null : () => _load(reset: true),
                      appearance: MakoloActionAppearance.quiet,
                    ),
                  ),
                ],
                const SizedBox(height: 18),
                Text('Points accessibles', style: themed.textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(
                  'Retrouvez les informations et décisions passées.',
                  style: themed.textTheme.bodySmall,
                ),
                const SizedBox(height: 10),
                if (_nextCursor != null && !_loading && _error == null)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: MakoloActionButton(
                      key: const Key('conversation-history-more'),
                      label: 'Voir les Points plus anciens',
                      onPressed: () => _load(),
                      icon: Icons.keyboard_arrow_up_rounded,
                      appearance: MakoloActionAppearance.quiet,
                    ),
                  ),
                if (_loading && _rows.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(22),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (_rows.isEmpty && _initialAttempted && _error == null)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 24),
                    child: Text('Aucun Point accessible pour ce filtre.'),
                  ),
                ..._chronologicalHistory(context),
                if (_loading && _rows.isNotEmpty)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.all(12),
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _HistoricalCompletedGroup extends StatelessWidget {
  const _HistoricalCompletedGroup({
    super.key,
    required this.rows,
    required this.onOpenPoint,
  });

  final List<Map<String, dynamic>> rows;
  final ValueChanged<String> onOpenPoint;

  @override
  Widget build(BuildContext context) {
    final latest = rows.last;
    final summary = latest['timeline_summary']?.toString() ?? '';
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ExpansionTile(
        key: PageStorageKey<String>(
          'history-expand-${rows.first['id']}-${rows.last['id']}',
        ),
        leading: const Icon(Icons.task_alt_rounded),
        title: Text(
          rows.length == 1 ? 'Point terminé' : '${rows.length} Points terminés',
        ),
        subtitle: Text(
          summary.isEmpty ? 'Résultats accessibles' : summary,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        childrenPadding: const EdgeInsets.symmetric(horizontal: 12),
        children: [
          for (final row in rows)
            _HistoricalPointRow(
              key: ValueKey('history-expanded-${row['id']}'),
              row: row,
              onOpenRelated: onOpenPoint,
              onOpen: () {
                final id = row['id']?.toString();
                if (id != null && id.isNotEmpty) onOpenPoint(id);
              },
            ),
        ],
      ),
    );
  }
}

class _HistoricalPointRow extends StatelessWidget {
  const _HistoricalPointRow({
    super.key,
    required this.row,
    required this.onOpen,
    required this.onOpenRelated,
  });
  final Map<String, dynamic> row;
  final VoidCallback onOpen;
  final ValueChanged<String> onOpenRelated;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final kind = switch (row['kind']?.toString()) {
      'poll' => 'Sondage',
      'confirmation' => 'Confirmation',
      'form_request' => 'Formulaire',
      'request' => 'Demande',
      'question' => 'Question',
      'exchange' => 'Échange',
      _ => 'Information',
    };
    final lifecycle = switch (row['lifecycle']?.toString()) {
      'resolved' => 'Terminé',
      'superseded' => 'Remplacé',
      'expired' => 'Expiré',
      'cancelled' => 'Annulé',
      'response_closed' => 'Réponses closes',
      _ => '',
    };
    final title = row['title']?.toString() ?? '';
    final resolution = row['resolution_summary']?.toString() ?? '';
    final subtitle = row['body']?.toString() ?? '';
    final replacement = row['replaced_by_point_id']?.toString();
    final time = DateTime.tryParse(row['published_at']?.toString() ?? '')
        ?.toLocal();
    final author = row['author'];
    final mine = author is Map && author['is_mine'] == true;
    return Semantics(
      button: true,
      label: [
        kind,
        title,
        lifecycle,
        resolution,
        'Ouvrir le Point',
      ].where((v) => v.isNotEmpty).join(', '),
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          key: Key('conversation-history-point-${row['id']}'),
          onTap: onOpen,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 6),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  lifecycle.isEmpty ? kind : '$kind · $lifecycle',
                  style: theme.textTheme.labelMedium,
                ),
                const SizedBox(height: 5),
                Text(
                  title.isEmpty ? kind : title,
                  style: theme.textTheme.titleMedium,
                ),
                if (resolution.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text('✓ $resolution'),
                  )
                else if (subtitle.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      subtitle,
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                if (replacement != null && replacement.isNotEmpty)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: MakoloActionButton(
                      label: 'Voir le Point actuel',
                      onPressed: () => onOpenRelated(replacement),
                      icon: Icons.call_made_rounded,
                      appearance: MakoloActionAppearance.quiet,
                    ),
                  ),
                if (time != null)
                  Align(
                    alignment: Alignment.bottomRight,
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          MaterialLocalizations.of(context).formatTimeOfDay(
                            TimeOfDay.fromDateTime(time),
                            alwaysUse24HourFormat: true,
                          ),
                          style: theme.textTheme.labelSmall,
                        ),
                        if (mine) ...[
                          const SizedBox(width: 5),
                          const Tooltip(
                            message: 'Publication confirmée',
                            child: Icon(Icons.check_rounded, size: 15),
                          ),
                        ],
                      ],
                    ),
                  ),
                const Divider(height: 24),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
