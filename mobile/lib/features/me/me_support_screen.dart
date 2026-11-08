import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/owner_source_state.dart';

/// Read-only personal support index. Recognition, Loyalty and Partner stay
/// separate owner domains; this surface does not invent client mutations.
class MeSupportScreen extends StatelessWidget {
  const MeSupportScreen({super.key, required this.personal});

  final PersonalRepository personal;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mes appuis')),
      body: StreamBuilder<OwnerSourceState>(
        stream: personal.watchMeSource(),
        initialData: OwnerSourceState.unknown,
        builder: (context, sourceSnapshot) {
          if (sourceSnapshot.data?.invalidated == true) {
            return const Center(
              child: Text('Mes appuis ne sont plus accessibles.'),
            );
          }
          return StreamBuilder<StoredProjection?>(
            stream: personal.watchMe(),
            builder: (context, snapshot) {
              final raw = snapshot.data?.payload['support'];
              if (raw is! Map) {
                return const Center(
                  child: Text('Mes appuis sont indisponibles.'),
                );
              }
              final rows = <Widget>[];
              for (final family in ['recognition', 'loyalty', 'partners']) {
                final value = raw[family];
                if (value is! Map || value['available'] != true) continue;
                final title = switch (family) {
                  'recognition' => 'Reconnaissance',
                  'loyalty' => 'Fidélité',
                  _ => 'Partenaires',
                };
                final subtitle = switch (family) {
                  'recognition' when value['needs_response'] == true =>
                    'Une réponse est attendue',
                  'recognition' => 'Reconnaissance disponible',
                  'loyalty' => 'Mes avantages de fidélité',
                  _ => 'Mes relations partenaires',
                };
                rows.add(
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(switch (family) {
                      'recognition' => Icons.workspace_premium_outlined,
                      'loyalty' => Icons.card_giftcard_outlined,
                      _ => Icons.handshake_outlined,
                    }, color: Theme.of(context).colorScheme.primary),
                    title: Text(title),
                    subtitle: Text(subtitle),
                  ),
                );
              }
              return ListView(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                children: rows.isEmpty
                    ? const [
                        Padding(
                          padding: EdgeInsets.symmetric(vertical: 24),
                          child: Center(
                            child: Text(
                              'Aucun appui disponible pour le moment.',
                            ),
                          ),
                        ),
                      ]
                    : rows,
              );
            },
          );
        },
      ),
    );
  }
}
