import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/local/profile_store.dart';
import '../../repositories/personal_repository.dart';
import '../../presentation/humanization.dart';
import 'ongoing_presentation.dart';

/// Calendar of owner-established human moments for admitted personal pursuits.
/// It consumes the same profile-bound local-first projection as En cours.
class OngoingCalendarScreen extends StatelessWidget {
  const OngoingCalendarScreen({super.key, required this.repository});

  final PersonalRepository repository;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Calendrier')),
    body: StreamBuilder<StoredProjection?>(
      stream: repository.watchOngoing(),
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
        if (events.isEmpty) {
          return const Center(child: Text('Aucune date à afficher pour le moment.'));
        }
        final stale = projection.freshUntil != null &&
            projection.freshUntil!.isBefore(DateTime.now().toUtc());
        return ListView.separated(
          key: const PageStorageKey<String>('ongoing-calendar'),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
          itemCount: events.length + (stale ? 1 : 0),
          separatorBuilder: (_, _) => const Divider(height: 24),
          itemBuilder: (context, index) {
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
