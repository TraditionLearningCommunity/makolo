import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/local/profile_store.dart';
import '../../repositories/personal_repository.dart';
import '../../network/makolo_api_client.dart';
import '../../presentation/humanization.dart';
import 'ongoing_presentation.dart';

/// Calendar of owner-established human moments for admitted personal pursuits.
/// It consumes the same profile-bound local-first projection as En cours.
class OngoingCalendarScreen extends StatefulWidget {
  const OngoingCalendarScreen({super.key, required this.repository, this.api});

  final PersonalRepository repository;
  final MakoloApiClient? api;

  @override
  State<OngoingCalendarScreen> createState() => _OngoingCalendarScreenState();
}

class _OngoingCalendarScreenState extends State<OngoingCalendarScreen> {
  late Stream<StoredProjection?> _projectionStream;
  bool _loadingMore = false;
  String? _loadError;

  Future<void> _loadMore(StoredProjection current) async {
    if (_loadingMore || widget.api == null) return;
    setState(() { _loadingMore = true; _loadError = null; });
    try {
      await widget.repository.loadMoreOngoing(api: widget.api!, current: current);
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
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Calendrier')),
    body: StreamBuilder<StoredProjection?>(
      stream: _projectionStream,
      builder: (context, snapshot) {
        final projection = snapshot.data;
        if (projection == null) {
          if (snapshot.hasError) {
            return const Center(child: Text('Calendrier indisponible.'));
          }
          return const Center(child: CircularProgressIndicator.adaptive());
        }
        final events = <_OngoingMoment>[];
        for (final item in OngoingContinuityPresentation.fromProjection(projection)) {
          for (final fact in item.temporalFacts) {
            final raw = fact['at'] ?? fact['date'];
            final instant = MakoloHumanization.tryParseInstant(raw);
            if (instant == null) continue;
            events.add(_OngoingMoment(
              at: instant,
              hasTime: fact['at'] != null,
              title: item.title,
              label: fact['label'] is String ? fact['label'] as String : 'À venir',
              id: item.id,
            ));
          }
        }
        events.sort((a, b) {
          final order = a.at.compareTo(b.at);
          return order != 0 ? order : a.title.compareTo(b.title);
        });
        final continuation = projection.payload['continuation'];
        final token = continuation is Map ? continuation['token'] : null;
        final hasMore = token is String && token.isNotEmpty;
        if (events.isEmpty && !hasMore) {
          return const Center(child: Text('Aucune date à afficher pour le moment.'));
        }
        final stale = projection.freshUntil != null &&
            projection.freshUntil!.isBefore(DateTime.now().toUtc());
        return ListView.separated(
          key: const PageStorageKey<String>('ongoing-calendar'),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
          itemCount: events.length + (stale ? 1 : 0) + (hasMore ? 1 : 0),
          separatorBuilder: (_, _) => const Divider(height: 24),
          itemBuilder: (context, index) {
            if (hasMore && index == events.length + (stale ? 1 : 0)) {
              return Center(
                child: _loadingMore
                    ? const CircularProgressIndicator.adaptive()
                    : TextButton.icon(
                        onPressed: widget.api == null ? null : () => _loadMore(projection),
                        icon: const Icon(Icons.expand_more_rounded),
                        label: Text(_loadError ?? 'Afficher les autres dates'),
                      ),
              );
            }
            if (stale && index == 0) {
              return const ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(Icons.history_rounded),
                title: Text('Dernières dates connues'),
                subtitle: Text('À confirmer après actualisation.'),
              );
            }
            final event = events[stale ? index - 1 : index];
            final date = event.hasTime
                ? MakoloHumanization.formatDateTime(event.at, now: DateTime.now())
                : MakoloHumanization.formatShortDate(event.at);
            return Semantics(
              label: '${event.title}. ${event.label}. $date',
              child: ListTile(
                contentPadding: EdgeInsets.zero,
                key: ValueKey('ongoing-moment-${event.id}-$index'),
                leading: const Icon(Icons.event_outlined),
                title: Text(event.title),
                subtitle: Text(event.label),
                trailing: Text(date, style: Theme.of(context).textTheme.labelMedium),
                onTap: () => context.push(
                  '/ongoing?continuity=${Uri.encodeQueryComponent(event.id)}',
                ),
              ),
            );
          },
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
