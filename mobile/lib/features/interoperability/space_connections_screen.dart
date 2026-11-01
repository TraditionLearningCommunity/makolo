import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../repositories/interoperability_repository.dart';
import 'intelligence_connection_controls.dart';

/// Space Connections are a server-authorized, online-only view until the
/// existing SpaceSync owner has a scoped Z16 source. Never cache it as Profile.
class SpaceConnectionsScreen extends StatefulWidget {
  const SpaceConnectionsScreen({
    super.key,
    required this.runtime,
    required this.slug,
  });

  final AppRuntime runtime;
  final String slug;

  @override
  State<SpaceConnectionsScreen> createState() => _SpaceConnectionsScreenState();
}

class _SpaceConnectionsScreenState extends State<SpaceConnectionsScreen> {
  bool loading = true;
  bool authorized = false;
  String? error;
  String? loadedId;
  int generation = 0;
  List<InteroperabilityConnectionProjection> connections = const [];

  SpaceActorContext? get actor {
    final current = widget.runtime.actorContext?.value;
    if (current is SpaceActorContext && current.space.slug == widget.slug) {
      return current;
    }
    return null;
  }

  String get root =>
      'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/';

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_actorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => unawaited(_load()));
  }

  void _actorChanged() {
    generation++;
    if (!mounted) return;
    setState(() {
      authorized = false;
      loading = true;
      loadedId = null;
      connections = const [];
    });
    unawaited(_load());
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_actorChanged);
    super.dispose();
  }

  Future<void> _load() async {
    final version = ++generation;
    final current = actor;
    final api = widget.runtime.api;
    if (current == null || api == null) {
      if (mounted) setState(() { authorized = false; loading = false; });
      return;
    }
    final id = current.space.id;
    setState(() {
      authorized = false;
      loading = true;
      error = null;
      connections = const [];
    });
    try {
      final payload = (await api.get('${root}interoperability/')).jsonObject();
      if (payload['schema_version'] != 'z16.v1' || payload['context'] != 'space') {
        throw const FormatException('Unexpected Space interop projection');
      }
      final rows = payload['connections'];
      if (rows is! List) throw const FormatException('Connections missing');
      if (!mounted || generation != version || actor?.space.id != id) return;
      setState(() {
        connections = rows.whereType<Map<String, dynamic>>()
            .map(InteroperabilityConnectionProjection.fromJson)
            .where((row) => row.scope == 'space')
            .toList(growable: false);
        authorized = true;
        loadedId = id;
        loading = false;
      });
    } on Object {
      if (!mounted || generation != version || actor?.space.id != id) return;
      setState(() {
        authorized = false;
        connections = const [];
        loading = false;
        error = 'Connexion au Space impossible ou autorité non confirmée. '
            'Les données ne sont pas conservées sur cet écran.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = actor;
    return Scaffold(
      appBar: AppBar(title: const Text('Connexions du Space')),
      body: current == null
          ? const Center(child: Text('Choisissez un Espace autorisé.'))
          : loading
          ? const Center(child: CircularProgressIndicator())
          : !authorized || loadedId != current.space.id
          ? ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text(error ?? 'Autorité à vérifier.'),
                TextButton.icon(
                  onPressed: _load,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Réessayer'),
                ),
              ],
            )
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(20),
                physics: const AlwaysScrollableScrollPhysics(),
                children: [
                  Text(
                    'Ces relations appartiennent à cet Espace. '
                    'Le serveur vérifie space.manage pour chaque opération.',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  if (connections.isEmpty)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 24),
                      child: Text('Aucune connexion de cet Espace.'),
                    ),
                  for (final row in connections)
                    Card(
                      child: ListTile(
                        leading: const Icon(Icons.link_outlined),
                        title: Text(row.displayName),
                        subtitle: Text(!row.enabled
                            ? 'Désactivée'
                            : row.usable
                            ? 'Connectée et disponible'
                            : 'Reliée · disponibilité à vérifier'),
                      ),
                    ),
                  IntelligenceConnectionControls(
                    runtime: widget.runtime,
                    path: '${root}intelligence/connections/',
                    connections: connections,
                    onChanged: _load,
                  ),
                ],
              ),
            ),
    );
  }
}
