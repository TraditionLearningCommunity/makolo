import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../design/makolo_theme.dart';
import '../space/space_repository.dart';

/// Local copy inventory only. It does not assert current server authority.
class OfflineDataScreen extends StatefulWidget {
  const OfflineDataScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  State<OfflineDataScreen> createState() => _OfflineDataScreenState();
}

class _OfflineDataScreenState extends State<OfflineDataScreen> {
  late Future<List<_LocalCopy>> _copies = _readCopies();

  Future<List<_LocalCopy>> _readCopies() async {
    final store = widget.runtime.store;
    if (store == null) return const [];
    const personal = <(String, String)>[
      ('personal.me', 'Moi'),
      ('personal.now', 'Maintenant'),
      ('personal.ongoing', 'En cours'),
    ];
    final sources = [
      ...personal,
      (SpaceSyncKeys.inventoryProjectionKind, 'Mes Espaces'),
    ];
    final snapshots = await Future.wait(
      sources.map((source) => store.readProjection(source.$1)),
    );
    return [
      for (var i = 0; i < sources.length; i++)
        _LocalCopy(sources[i].$2, snapshots[i]),
    ];
  }

  Future<void> _reload() async {
    setState(() => _copies = _readCopies());
    await _copies;
  }

  String _receivedAt(BuildContext context, DateTime date) {
    final local = date.toLocal();
    final formatter = MaterialLocalizations.of(context);
    final day = formatter.formatMediumDate(local);
    final time = formatter.formatTimeOfDay(TimeOfDay.fromDateTime(local));
    return '$day · $time';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Données hors ligne')),
      body: FutureBuilder<List<_LocalCopy>>(
        future: _copies,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator.adaptive());
          }
          if (snapshot.hasError) {
            return Center(
              child: TextButton.icon(
                onPressed: _reload,
                icon: const Icon(Icons.refresh_outlined),
                label: const Text('Réessayer la lecture locale'),
              ),
            );
          }
          final copies = snapshot.data ?? const <_LocalCopy>[];
          return RefreshIndicator(
            onRefresh: _reload,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(MakoloSpacing.inner),
              children: [
                Text(
                  'Ces informations décrivent uniquement les copies déjà '
                  'présentes sur cet appareil. Elles ne prouvent pas que '
                  'les données, droits ou responsabilités sont encore actuels.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: MakoloSpacing.md),
                if (copies.isEmpty)
                  const ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text('Stockage personnel indisponible'),
                    subtitle: Text('Aucune information locale à présenter.'),
                  ),
                for (final copy in copies)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(
                      copy.snapshot == null
                          ? Icons.cloud_off_outlined
                          : Icons.offline_pin_outlined,
                    ),
                    title: Text(copy.label),
                    subtitle: Text(
                      copy.snapshot == null
                          ? 'Aucune copie locale disponible'
                          : 'Copie reçue : ${_receivedAt(context, copy.snapshot!.receivedAt)}',
                    ),
                    trailing: copy.snapshot == null
                        ? null
                        : const Icon(Icons.check_circle_outline),
                  ),
                const SizedBox(height: MakoloSpacing.lg),
                const Text(
                  'Les changements d’acteur, permissions, mandats et actions '
                  'sensibles nécessitent une vérification serveur. '
                  'Une copie locale ne donne aucun nouveau droit.',
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _LocalCopy {
  const _LocalCopy(this.label, this.snapshot);

  final String label;
  final StoredProjection? snapshot;
}
