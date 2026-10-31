import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/local/profile_store.dart';
import '../../repositories/personal_repository.dart';
import '../../network/makolo_api_client.dart';
import '../../presentation/humanization.dart';
import 'ongoing_presentation.dart';

/// The calendar is only a temporal view of owner-established Ongoing facts.
/// It neither creates appointments nor changes their authority or lifecycle.
enum OngoingCalendarOrder { upcoming, oldest, newest }

List<T> sortOngoingCalendarMoments<T>(
  List<T> values, {
  required DateTime Function(T) dateOf,
  required String Function(T) titleOf,
  required DateTime now,
  OngoingCalendarOrder order = OngoingCalendarOrder.upcoming,
}) {
  final sorted = [...values];
  final today = DateUtils.dateOnly(now.toLocal());
  sorted.sort((a, b) {
    final left = dateOf(a).toLocal();
    final right = dateOf(b).toLocal();
    if (order == OngoingCalendarOrder.upcoming) {
      final leftUpcoming = !DateUtils.dateOnly(left).isBefore(today);
      final rightUpcoming = !DateUtils.dateOnly(right).isBefore(today);
      if (leftUpcoming != rightUpcoming) return leftUpcoming ? -1 : 1;
      final chronology = left.compareTo(right);
      if (chronology != 0) {
        return leftUpcoming ? chronology : -chronology;
      }
    } else {
      final chronology = left.compareTo(right);
      if (chronology != 0) {
        return order == OngoingCalendarOrder.oldest ? chronology : -chronology;
      }
    }
    return titleOf(a).compareTo(titleOf(b));
  });
  return sorted;
}

class OngoingCalendarScreen extends StatefulWidget {
  const OngoingCalendarScreen({super.key, required this.repository, this.api});

  final PersonalRepository repository;
  final MakoloApiClient? api;

  @override
  State<OngoingCalendarScreen> createState() => _OngoingCalendarScreenState();
}

class _OngoingCalendarScreenState extends State<OngoingCalendarScreen> {
  late Stream<StoredProjection?> _projectionStream;
  StoredProjection? _lastProjection;
  bool _loadingMore = false;
  String? _loadError;
  OngoingCalendarOrder _order = OngoingCalendarOrder.upcoming;
  DateTime? _specificDay;
  DateTimeRange? _period;

  Future<void> _loadMore(StoredProjection current) async {
    if (_loadingMore || widget.api == null) return;
    setState(() {
      _loadingMore = true;
      _loadError = null;
    });
    try {
      await widget.repository.loadMoreOngoing(
        api: widget.api!,
        current: current,
      );
    } on Object {
      if (mounted) {
        setState(() => _loadError = 'Impossible de charger la suite.');
      }
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  @override
  void initState() {
    super.initState();
    _projectionStream = widget.repository.watchOngoing();
  }

  @override
  void didUpdateWidget(covariant OngoingCalendarScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository) {
      _projectionStream = widget.repository.watchOngoing();
      _lastProjection = null;
    }
  }

  Future<void> _chooseDay() async {
    final today = DateUtils.dateOnly(DateTime.now());
    final selected = await showDatePicker(
      context: context,
      initialDate: _specificDay ?? today,
      firstDate: DateTime(1900),
      lastDate: DateTime(2100),
      helpText: 'Rechercher une date',
    );
    if (selected == null || !mounted) return;
    setState(() {
      _specificDay = DateUtils.dateOnly(selected);
      _period = null;
    });
  }

  Future<void> _choosePeriod() async {
    final selected = await showDateRangePicker(
      context: context,
      initialDateRange: _period,
      firstDate: DateTime(1900),
      lastDate: DateTime(2100),
      helpText: 'Choisir une période',
      saveText: 'Appliquer',
    );
    if (selected == null || !mounted) return;
    setState(() {
      _specificDay = null;
      _period = selected;
    });
  }

  void _resetPeriod() {
    setState(() {
      _specificDay = null;
      _period = null;
    });
  }

  bool _matchesDate(DateTime date) {
    final day = DateUtils.dateOnly(date.toLocal());
    if (_specificDay != null) {
      return DateUtils.isSameDay(day, _specificDay);
    }
    final period = _period;
    if (period == null) return true;
    return !day.isBefore(DateUtils.dateOnly(period.start)) &&
        !day.isAfter(DateUtils.dateOnly(period.end));
  }

  String get _orderLabel => switch (_order) {
    OngoingCalendarOrder.upcoming => 'Prochaines dates',
    OngoingCalendarOrder.oldest => 'Plus anciennes',
    OngoingCalendarOrder.newest => 'Plus récentes',
  };

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Calendrier'),
      actions: [
        PopupMenuButton<OngoingCalendarOrder>(
          key: const Key('ongoing-calendar-sort'),
          tooltip: 'Trier les dates',
          icon: const Icon(Icons.sort_rounded),
          initialValue: _order,
          onSelected: (value) => setState(() => _order = value),
          itemBuilder: (_) => const [
            PopupMenuItem(
              value: OngoingCalendarOrder.upcoming,
              child: Text('Prochaines dates d’abord'),
            ),
            PopupMenuItem(
              value: OngoingCalendarOrder.oldest,
              child: Text('Plus anciennes d’abord'),
            ),
            PopupMenuItem(
              value: OngoingCalendarOrder.newest,
              child: Text('Plus récentes d’abord'),
            ),
          ],
        ),
        PopupMenuButton<String>(
          key: const Key('ongoing-calendar-filter'),
          tooltip: 'Filtrer les dates',
          icon: const Icon(Icons.filter_list_rounded),
          onSelected: (value) {
            switch (value) {
              case 'day':
                _chooseDay();
              case 'range':
                _choosePeriod();
              case 'all':
                _resetPeriod();
            }
          },
          itemBuilder: (_) => const [
            PopupMenuItem(value: 'day', child: Text('Date précise')),
            PopupMenuItem(value: 'range', child: Text('Période')),
            PopupMenuItem(value: 'all', child: Text('Toutes les dates')),
          ],
        ),
      ],
    ),
    body: StreamBuilder<StoredProjection?>(
      stream: _projectionStream,
      builder: (context, snapshot) {
        if (!snapshot.hasError &&
            snapshot.connectionState == ConnectionState.active) {
          _lastProjection = snapshot.data;
        }
        final projection = snapshot.data ?? _lastProjection;
        if (projection == null) {
          if (snapshot.hasError) {
            return const Center(child: Text('Calendrier indisponible.'));
          }
          return const Center(child: CircularProgressIndicator.adaptive());
        }

        final allEvents = <_OngoingMoment>[];
        for (final item in OngoingContinuityPresentation.fromProjection(
          projection,
        )) {
          for (final fact in item.temporalFacts) {
            final raw = fact['at'] ?? fact['date'];
            final instant = MakoloHumanization.tryParseInstant(raw);
            if (instant == null) continue;
            allEvents.add(
              _OngoingMoment(
                at: instant,
                hasTime: fact['at'] != null,
                title: item.title,
                label: fact['label'] is String
                    ? fact['label'] as String
                    : 'Date à retenir',
                id: item.id,
              ),
            );
          }
        }

        final now = DateTime.now();
        final events = sortOngoingCalendarMoments(
          allEvents.where((event) => _matchesDate(event.at)).toList(),
          dateOf: (event) => event.at,
          titleOf: (event) => event.title,
          now: now,
          order: _order,
        );
        final continuation = projection.payload['continuation'];
        final token = continuation is Map ? continuation['token'] : null;
        final hasMore = token is String && token.isNotEmpty;
        final stale =
            projection.freshUntil != null &&
            projection.freshUntil!.isBefore(DateTime.now().toUtc());

        final filterLabel = _specificDay != null
            ? MakoloHumanization.formatLongDate(_specificDay!)
            : _period != null
            ? '${MakoloHumanization.formatLongDate(_period!.start)} – '
                  '${MakoloHumanization.formatLongDate(_period!.end)}'
            : null;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
              child: Wrap(
                spacing: 8,
                runSpacing: 4,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Chip(
                    key: const Key('ongoing-calendar-order-label'),
                    label: Text(_orderLabel),
                    avatar: const Icon(Icons.event_outlined, size: 18),
                    visualDensity: VisualDensity.compact,
                  ),
                  if (filterLabel != null)
                    InputChip(
                      key: const Key('ongoing-calendar-active-filter'),
                      label: Text(filterLabel),
                      onDeleted: _resetPeriod,
                      deleteIcon: const Icon(Icons.close, size: 18),
                      visualDensity: VisualDensity.compact,
                    ),
                ],
              ),
            ),
            if (stale)
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Text(
                  'Dernières dates connues · à confirmer après actualisation.',
                ),
              ),
            Expanded(
              child: events.isEmpty && !hasMore
                  ? Center(
                      child: Text(
                        allEvents.isEmpty
                            ? 'Aucune date à afficher pour le moment.'
                            : 'Aucune date dans cette sélection.',
                      ),
                    )
                  : ListView.separated(
                      key: const PageStorageKey<String>('ongoing-calendar'),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                      itemCount: events.length + (hasMore ? 1 : 0),
                      separatorBuilder: (_, _) => const Divider(height: 16),
                      itemBuilder: (context, index) {
                        if (index == events.length) {
                          return Center(
                            child: _loadingMore
                                ? const CircularProgressIndicator.adaptive()
                                : TextButton.icon(
                                    onPressed: widget.api == null
                                        ? null
                                        : () => _loadMore(projection),
                                    icon: const Icon(Icons.expand_more_rounded),
                                    label: Text(
                                      _loadError ?? 'Afficher les autres dates',
                                    ),
                                  ),
                          );
                        }
                        final event = events[index];
                        final date = event.hasTime
                            ? MakoloHumanization.formatDateTime(
                                event.at,
                                now: now,
                              )
                            : MakoloHumanization.formatDay(event.at, now: now);
                        return ListTile(
                          key: ValueKey('ongoing-moment-${event.id}-$index'),
                          contentPadding: EdgeInsets.zero,
                          minVerticalPadding: 10,
                          leading: const Icon(Icons.event_outlined),
                          title: Text(event.title),
                          subtitle: Text(event.label),
                          trailing: ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 138),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Flexible(
                                  child: Text(
                                    date,
                                    maxLines: 2,
                                    textAlign: TextAlign.end,
                                    style: Theme.of(context)
                                        .textTheme
                                        .labelMedium,
                                  ),
                                ),
                                const SizedBox(width: 4),
                                const Icon(
                                  Icons.chevron_right_rounded,
                                  size: 18,
                                ),
                              ],
                            ),
                          ),
                          // Calendar is a secondary route above the indexed
                          // personal shell. Pushing the shell's existing
                          // /ongoing page again can duplicate its Navigator
                          // page key (!keyReservation.contains(key)).
                          // Go to the canonical N2 destination instead.
                          onTap: () => context.go(
                            '/ongoing?continuity=${Uri.encodeQueryComponent(event.id)}',
                          ),
                        );
                      },
                    ),
            ),
          ],
        );
      },
    ),
  );
}

class _OngoingMoment {
  const _OngoingMoment({
    required this.at,
    required this.hasTime,
    required this.title,
    required this.label,
    required this.id,
  });
  final DateTime at;
  final bool hasTime;
  final String title;
  final String label;
  final String id;
}
