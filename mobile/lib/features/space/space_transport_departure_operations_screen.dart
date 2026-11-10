import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../presentation/contracts/space_presentation.dart';

/// Native MT5 N3. Transport owns every command; no optimistic local mutation.
/// A result of uncertain delivery must be re-read, never retried blindly.
class SpaceTransportDepartureOperationsScreen extends StatefulWidget {
  const SpaceTransportDepartureOperationsScreen({
    super.key,
    required this.runtime,
    required this.actor,
    required this.departureId,
  });

  final AppRuntime runtime;
  final SpaceActorContext actor;
  final String departureId;

  @override
  State<SpaceTransportDepartureOperationsScreen> createState() =>
      _SpaceTransportDepartureOperationsScreenState();
}

class _SpaceTransportDepartureOperationsScreenState
    extends State<SpaceTransportDepartureOperationsScreen> {
  final _start = TextEditingController();
  final _end = TextEditingController();
  final _timezone = TextEditingController();
  Map<String, dynamic>? _owner;
  bool _loading = true;
  bool _posting = false;
  bool _confirming = false;
  bool _requiresVerification = false;
  int _epoch = 0;
  int _vehiclesOffset = 0;
  String? _error;

  bool get _actorValid => widget.runtime.actorContext?.value == widget.actor;

  String get _path => Uri(
    path:
        'api/v1/organizations/workspaces/'
        '${Uri.encodeComponent(widget.actor.space.slug)}/work/g3/transport/'
        'departures/${Uri.encodeComponent(widget.departureId)}/operations/',
    queryParameters: {
      if (!widget.actor.perspective.isAll)
        'responsibility': widget.actor.perspective.id!,
      if (_vehiclesOffset > 0) 'vehicles_offset': '$_vehiclesOffset',
    },
  ).toString();

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_actorChanged);
    unawaited(_read());
  }

  @override
  void didUpdateWidget(covariant SpaceTransportDepartureOperationsScreen old) {
    super.didUpdateWidget(old);
    if (old.runtime.actorContext != widget.runtime.actorContext) {
      old.runtime.actorContext?.removeListener(_actorChanged);
      widget.runtime.actorContext?.addListener(_actorChanged);
    }
    if (old.runtime != widget.runtime ||
        old.actor != widget.actor ||
        old.departureId != widget.departureId) {
      _actorChanged();
    }
  }

  @override
  void dispose() {
    ++_epoch;
    widget.runtime.actorContext?.removeListener(_actorChanged);
    _start.dispose();
    _end.dispose();
    _timezone.dispose();
    super.dispose();
  }

  void _actorChanged() {
    ++_epoch;
    if (!mounted) return;
    setState(() {
      _owner = null;
      _error = null;
      _posting = false;
      _confirming = false;
      _requiresVerification = false;
      _vehiclesOffset = 0;
      _loading = _actorValid;
    });
    if (_actorValid) unawaited(_read());
  }

  bool _matches(Map<String, dynamic> payload) {
    final space = spaceMap(payload['space']);
    final owner = spaceMap(payload['owner']);
    return space?['id'] == widget.actor.space.id &&
        space?['slug'] == widget.actor.space.slug &&
        payload['responsibility'] == (widget.actor.perspective.id ?? 'all') &&
        owner?['kind'] == 'transport_departure' &&
        owner?['id'] == widget.departureId;
  }

  Future<void> _read() async {
    if (!_actorValid) return;
    final epoch = ++_epoch;
    setState(() {
      _loading = true;
      _owner = null;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Connexion indisponible');
      final response = await api.get(_path);
      if (response.statusCode != 200) {
        throw StateError('Départ non accessible');
      }
      final payload = response.jsonObject();
      if (!_matches(payload)) {
        throw const FormatException(
          'Propriétaire ou responsabilité incorrects',
        );
      }
      if (!mounted || !_actorValid || epoch != _epoch) return;
      final timing = spaceMap(payload['timing']);
      _start.text = spaceText(timing?['start_at']) ?? '';
      _end.text = spaceText(timing?['end_at']) ?? '';
      _timezone.text = spaceText(timing?['timezone']) ?? '';
      setState(() {
        _owner = payload;
        _requiresVerification = false;
      });
    } on Object {
      if (mounted && _actorValid && epoch == _epoch) {
        setState(() {
          _error =
              'Ce départ ne peut pas être consulté maintenant. '
              'Vérifiez la connexion et votre autorité.';
        });
      }
    } finally {
      if (mounted && epoch == _epoch) setState(() => _loading = false);
    }
  }

  void _pageVehicles(int offset) {
    if (!_actorValid || _posting || offset < 0 || offset > 10000) return;
    setState(() => _vehiclesOffset = offset);
    unawaited(_read());
  }

  Future<void> _command(String action, {String? vehicleId}) async {
    if (_owner == null ||
        !_actorValid ||
        _loading ||
        _posting ||
        _confirming ||
        _requiresVerification) {
      return;
    }
    final title = switch (action) {
      'assign_vehicle' => 'Affecter ce véhicule ?',
      'reschedule' => 'Reprogrammer ce départ ?',
      _ => 'Annuler ce départ ?',
    };
    setState(() => _confirming = true);
    final accepted = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(title),
        content: Text(switch (action) {
          'assign_vehicle' => 'Le véhicule choisi sera affecté à ce départ.',
          'reschedule' => 'Les horaires de ce départ seront modifiés.',
          _ => 'Ce départ sera annulé.',
        }),
        actions: [
          MakoloActionButton(
            label: 'Retour',
            appearance: MakoloActionAppearance.quiet,
            onPressed: () => Navigator.pop(dialogContext, false),
          ),
          MakoloActionButton(
            label: 'Confirmer',
            appearance: MakoloActionAppearance.primary,
            onPressed: () => Navigator.pop(dialogContext, true),
          ),
        ],
      ),
    );
    if (!mounted || !_actorValid) return;
    setState(() => _confirming = false);
    if (accepted != true) return;
    final epoch = _epoch;
    setState(() {
      _posting = true;
      _requiresVerification = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Connexion indisponible');
      final body = <String, dynamic>{
        'action': action,
        if (action == 'assign_vehicle') 'vehicle': vehicleId,
        if (action == 'reschedule') ...{
          'timezone': _timezone.text.trim(),
          'start_at': _start.text.trim(),
          if (_end.text.trim().isNotEmpty) 'end_at': _end.text.trim(),
        },
        if (action == 'cancel') 'confirmed': true,
      };
      final response = await api.post(_path, body: body);
      if (response.statusCode != 200) throw StateError('Non confirmé');
      final payload = response.jsonObject();
      if (!_matches(payload) || payload['confirmed_by_owner'] != true) {
        throw const FormatException('Réponse non confirmée');
      }
      if (!mounted || !_actorValid || epoch != _epoch) return;
      // _read increments the epoch. Release the command guard before it,
      // while keeping actions disabled until the owner confirms the reload.
      setState(() => _posting = false);
      await _read();
    } on Object {
      if (mounted && _actorValid && epoch == _epoch) {
        setState(() {
          _owner = null;
          _error =
              'Impossible de confirmer le résultat. Actualisez ce départ avant '
              'de réessayer pour éviter une opération en double.';
        });
      }
    } finally {
      if (mounted && epoch == _epoch) setState(() => _posting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final data = _owner;
    final flags = spaceMap(data?['actions']);
    final vehicle = spaceMap(data?['vehicle']);
    final capacity = spaceMap(data?['capacity']);
    final vehicles = spaceMap(data?['vehicles']);
    final rows = vehicles?['items'] is List
        ? vehicles!['items'] as List
        : const [];
    final offset = vehicles?['offset'] is int ? vehicles!['offset'] as int : 0;
    final limit = vehicles?['limit'] is int ? vehicles!['limit'] as int : 60;

    return Scaffold(
      appBar: AppBar(title: const Text('Exploiter un départ')),
      body: !_actorValid
          ? const Center(child: Text('Sélectionnez votre Espace autorisé.'))
          : RefreshIndicator(
              onRefresh: _read,
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  if (_loading) const LinearProgressIndicator(),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(
                        _error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ),
                  if (data == null)
                    MakoloActionButton(
                      label: 'Actualiser les autorisations',
                      appearance: MakoloActionAppearance.secondary,
                      onPressed: _loading || _posting ? null : _read,
                    ),
                  if (data != null) ...[
                    Text(
                      spaceText(data['title']) ?? 'Départ',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'État : ${spaceStateLabel(spaceText(data['status']) ?? 'unknown')}',
                    ),
                    ListTile(
                      title: const Text('Véhicule affecté'),
                      subtitle: Text(
                        spaceText(vehicle?['label']) ??
                            'Aucun véhicule affecté',
                      ),
                    ),
                    if (capacity != null)
                      ListTile(
                        title: const Text('Places disponibles à la vente'),
                        subtitle: Text(
                          capacity['unlimited'] == true
                              ? 'Aucune limite renseignée'
                              : capacity['available'] == null
                              ? 'Disponibilité à vérifier'
                              : "${capacity['available']} ${capacity['available'].toString() == '1' ? 'place disponible' : 'places disponibles'}",
                        ),
                      ),
                    if (flags?['can_assign_vehicle'] == true) ...[
                      const SizedBox(height: 14),
                      Text(
                        'Affecter un véhicule',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      for (final raw in rows)
                        if (spaceMap(raw) case final Map<String, dynamic> row)
                          ListTile(
                            title: Text(spaceText(row['label']) ?? 'Véhicule'),
                            subtitle: Text(
                              '${row['physical_capacity']} places physiques',
                            ),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: _posting || _confirming || _requiresVerification
                                ? null
                                : () => _command(
                                    'assign_vehicle',
                                    vehicleId: spaceText(row['id']),
                                  ),
                          ),
                      Wrap(
                        spacing: 8,
                        children: [
                          if (offset > 0)
                            MakoloActionButton(
                              appearance: MakoloActionAppearance.secondary,
                              onPressed: _posting
                                  ? null
                                  : () => _pageVehicles(
                                      offset > limit ? offset - limit : 0,
                                    ),
                              label: 'Véhicules précédents',
                            ),
                          if (vehicles?['has_more'] == true)
                            MakoloActionButton(
                              appearance: MakoloActionAppearance.secondary,
                              onPressed: _posting
                                  ? null
                                  : () => _pageVehicles(offset + limit),
                              label: 'Véhicules suivants',
                            ),
                        ],
                      ),
                    ],
                    if (flags?['can_reschedule'] == true) ...[
                      const SizedBox(height: 16),
                      Text(
                        'Reprogrammer',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      TextField(
                        controller: _timezone,
                        enabled: !_posting && !_requiresVerification,
                        decoration: const InputDecoration(
                          labelText: 'Fuseau horaire IANA',
                        ),
                      ),
                      TextField(
                        controller: _start,
                        enabled: !_posting && !_requiresVerification,
                        decoration: const InputDecoration(
                          labelText: 'Départ ISO 8601',
                        ),
                      ),
                      TextField(
                        controller: _end,
                        enabled: !_posting && !_requiresVerification,
                        decoration: const InputDecoration(
                          labelText: 'Arrivée ISO 8601 (facultative)',
                        ),
                      ),
                      MakoloActionButton(
                        label: 'Confirmer la reprogrammation',
                        appearance: MakoloActionAppearance.primary,
                        phase: _posting
                            ? MakoloActionPhase.processing
                            : _requiresVerification
                            ? MakoloActionPhase.failed
                            : _confirming
                            ? MakoloActionPhase.unavailable
                            : MakoloActionPhase.available,
                        onPressed: _posting || _confirming || _requiresVerification
                            ? null
                            : () => _command('reschedule'),
                      ),
                    ],
                    if (flags?['can_cancel'] == true) ...[
                      const SizedBox(height: 20),
                      MakoloActionButton(
                        label: 'Annuler ce départ',
                        appearance: MakoloActionAppearance.danger,
                        icon: Icons.cancel_outlined,
                        phase: _posting
                            ? MakoloActionPhase.processing
                            : _requiresVerification
                            ? MakoloActionPhase.failed
                            : _confirming
                            ? MakoloActionPhase.unavailable
                            : MakoloActionPhase.available,
                        onPressed: _posting || _confirming || _requiresVerification
                            ? null
                            : () => _command('cancel'),
                      ),
                    ],
                    const SizedBox(height: 18),
                    MakoloActionButton(
                      label: 'Relire le départ',
                      appearance: MakoloActionAppearance.secondary,
                      onPressed: _loading || _posting ? null : _read,
                    ),
                    MakoloActionButton(
                      label: 'Retour au départ',
                      appearance: MakoloActionAppearance.quiet,
                      onPressed: () => context.pop(),
                    ),
                  ],
                ],
              ),
            ),
    );
  }
}
