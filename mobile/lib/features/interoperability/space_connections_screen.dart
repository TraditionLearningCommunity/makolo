import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../repositories/interoperability_repository.dart';
import '../../sync/sync_status.dart';
import 'intelligence_connection_controls.dart';
import 'interoperability_presentation.dart';

/// Same human labels as Profile and Web; technical health is not authority.
String spaceConnectionStatus(InteroperabilityConnectionProjection row) =>
    connectionStatusLabel(row);

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
  List<DomainIntegrationProjection> domainIntegrations = const [];

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
      domainIntegrations = const [];
    });
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant SpaceConnectionsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.runtime, widget.runtime) ||
        oldWidget.slug != widget.slug) {
      oldWidget.runtime.actorContext?.removeListener(_actorChanged);
      widget.runtime.actorContext?.addListener(_actorChanged);
      _actorChanged();
    }
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_actorChanged);
    super.dispose();
  }

  Future<void> _refreshAndConfirm() async {
    final expected = actor?.space.id;
    if (expected == null) throw StateError('Autorité Space indisponible.');
    await _load();
    if (!authorized || loadedId != expected || actor?.space.id != expected) {
      throw StateError('Autorité Space non confirmée après actualisation.');
    }
  }

  Future<void> _load() async {
    final version = ++generation;
    final current = actor;
    final api = widget.runtime.api;
    if (current == null || api == null) {
      if (mounted) {
        setState(() {
          authorized = false;
          loading = false;
        });
      }
      return;
    }
    final id = current.space.id;
    setState(() {
      authorized = false;
      loading = true;
      error = null;
      connections = const [];
      domainIntegrations = const [];
    });
    try {
      final payload = (await api.get('${root}interoperability/')).jsonObject();
      if (payload['schema_version'] != 'z16.v1' ||
          payload['context'] != 'space') {
        throw const FormatException('Unexpected Space interop projection');
      }
      final rows = payload['connections'];
      final ownerRows = payload['domain_integrations'];
      if (rows is! List) throw const FormatException('Connections missing');
      if (ownerRows != null && ownerRows is! List) {
        throw const FormatException('Domain owner integrations invalid');
      }
      if (!mounted || generation != version || actor?.space.id != id) return;
      setState(() {
        connections = rows
            .whereType<Map<String, dynamic>>()
            .map(InteroperabilityConnectionProjection.fromJson)
            .where((row) => row.scope == 'space')
            .toList(growable: false);
        domainIntegrations = (ownerRows is List ? ownerRows : const [])
            .whereType<Map<String, dynamic>>()
            .map(DomainIntegrationProjection.fromJson)
            .where(
              (row) =>
                  row.owner == 'payments' &&
                  row.kind == 'processing_capability',
            )
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
        domainIntegrations = const [];
        loadedId = null;
        loading = false;
        error = 'Impossible d’afficher les connexions de cet Espace.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = actor;
    final syncState = SyncStatusScope.maybeOf(context)?.state;
    final freshOwner =
        authorized &&
        current != null &&
        loadedId == current.space.id &&
        !loading;
    final canMutate =
        freshOwner &&
        widget.runtime.api != null &&
        syncState != SyncVisualState.offline &&
        syncState != SyncVisualState.failed &&
        syncState != SyncVisualState.stale &&
        syncState != SyncVisualState.conflict &&
        syncState != SyncVisualState.syncing;
    return Scaffold(
      appBar: AppBar(title: const Text('Connexions de l’Espace')),
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
                    'Services reliés à cet Espace.',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  IntelligenceConnectionControls(
                    key: ValueKey('space-connections-${current.space.id}'),
                    runtime: widget.runtime,
                    path: '${root}intelligence/connections/',
                    connections: connections,
                    mutationsEnabled: canMutate,
                    onChanged: _refreshAndConfirm,
                  ),
                ],
              ),
            ),
    );
  }
}
