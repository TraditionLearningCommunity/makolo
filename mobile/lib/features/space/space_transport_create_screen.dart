import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../presentation/contracts/space_presentation.dart';

/// MT5 native Transport creation. Owner services, not this widget, create
/// Route/Vehicle/Activity/Occurrence/CapacityPool/Offer in one transaction.
class SpaceTransportCreateScreen extends StatefulWidget {
  const SpaceTransportCreateScreen({
    super.key,
    required this.runtime,
    required this.actor,
  });

  final AppRuntime runtime;
  final SpaceActorContext actor;

  @override
  State<SpaceTransportCreateScreen> createState() =>
      _SpaceTransportCreateScreenState();
}

class _SpaceTransportCreateScreenState
    extends State<SpaceTransportCreateScreen> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _code = TextEditingController();
  final _registration = TextEditingController();
  final _capacity = TextEditingController();
  final _title = TextEditingController();
  final _start = TextEditingController();
  final _end = TextEditingController();
  final _timezone = TextEditingController();
  final _fareName = TextEditingController(text: 'Standard');
  final _price = TextEditingController(text: '0.00');
  final _currency = TextEditingController(text: 'USD');
  final _boarding = TextEditingController();
  final _reference = TextEditingController();

  String _kind = 'departure';
  String? _route;
  String? _vehicle;
  String? _origin;
  String? _destination;
  String _vehicleType = 'bus';
  String _mode = 'upfront';
  bool _publish = false;
  bool _loading = true;
  bool _submitting = false;
  bool _attempted = false;
  String? _error;
  int _epoch = 0;

  List<Map<String, dynamic>> _routes = [];
  List<Map<String, dynamic>> _vehicles = [];
  List<Map<String, dynamic>> _places = [];
  bool _moreRoutes = false;
  bool _moreVehicles = false;
  bool _morePlaces = false;
  bool _canCreateDeparture = false;

  bool get _actorValid =>
      widget.runtime.actorContext?.value == widget.actor &&
      widget.actor.perspective.isAll;

  String get _path =>
      'api/v1/organizations/workspaces/'
      '${Uri.encodeComponent(widget.actor.space.slug)}'
      '/work/g3/transport/create/';

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_onActorChange);
    unawaited(_loadOptions());
  }

  @override
  void didUpdateWidget(covariant SpaceTransportCreateScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChange);
      widget.runtime.actorContext?.addListener(_onActorChange);
    }
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.actor != widget.actor) {
      _onActorChange();
    }
  }

  @override
  void dispose() {
    ++_epoch;
    widget.runtime.actorContext?.removeListener(_onActorChange);
    for (final controller in [
      _name,
      _code,
      _registration,
      _capacity,
      _title,
      _start,
      _end,
      _timezone,
      _fareName,
      _price,
      _currency,
      _boarding,
      _reference,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  void _onActorChange() {
    ++_epoch;
    if (!mounted) return;
    setState(() {
      _routes = [];
      _vehicles = [];
      _places = [];
      _loading = _actorValid;
      _submitting = false;
      _attempted = false;
      _error = null;
    });
    if (_actorValid) unawaited(_loadOptions());
  }

  List<Map<String, dynamic>> _rows(dynamic value) => [
    if (value is List)
      for (final row in value)
        if (spaceMap(row) case final Map<String, dynamic> map) map,
  ];

  Future<void> _loadOptions({String? more}) async {
    if (!_actorValid || _submitting) return;
    final epoch = ++_epoch;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Connexion indisponible');
      final query = {
        if (more == 'routes') 'routes_offset': '${_routes.length}',
        if (more == 'vehicles') 'vehicles_offset': '${_vehicles.length}',
        if (more == 'places') 'places_offset': '${_places.length}',
      };
      final path = Uri(path: _path, queryParameters: query).toString();
      final response = await api.get(path);
      if (response.statusCode != 200) {
        throw StateError('Options Transport indisponibles');
      }
      final data = response.jsonObject();
      final space = spaceMap(data['space']);
      final caps = spaceMap(data['capabilities']);
      if (space?['id'] != widget.actor.space.id ||
          space?['slug'] != widget.actor.space.slug ||
          data['responsibility'] != 'all' ||
          caps?['create_route'] != true ||
          caps?['create_vehicle'] != true) {
        throw const FormatException('Transport owner mismatch');
      }
      final routes = spaceMap(data['routes']);
      final vehicles = spaceMap(data['vehicles']);
      final places = spaceMap(data['places']);
      if (routes == null || vehicles == null || places == null) {
        throw const FormatException('Options manquantes');
      }
      if (!mounted || !_actorValid || epoch != _epoch) return;
      setState(() {
        if (more == null || more == 'routes') {
          _routes = more == 'routes'
              ? [..._routes, ..._rows(routes['items'])]
              : _rows(routes['items']);
          _moreRoutes = routes['has_more'] == true;
        }
        if (more == null || more == 'vehicles') {
          _vehicles = more == 'vehicles'
              ? [..._vehicles, ..._rows(vehicles['items'])]
              : _rows(vehicles['items']);
          _moreVehicles = vehicles['has_more'] == true;
        }
        if (more == null || more == 'places') {
          _places = more == 'places'
              ? [..._places, ..._rows(places['items'])]
              : _rows(places['items']);
          _morePlaces = places['has_more'] == true;
        }
        _canCreateDeparture = caps?['create_departure'] == true;
        if (!_canCreateDeparture && _kind == 'departure') {
          _kind = 'route';
        }
      });
    } on Object {
      if (mounted && _actorValid && epoch == _epoch) {
        setState(() {
          _error = 'Impossible de relire les options Transport de cet Espace.';
        });
      }
    } finally {
      if (mounted && epoch == _epoch) setState(() => _loading = false);
    }
  }

  Future<void> _pickDateTime(TextEditingController field) async {
    if (_attempted) return;
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      firstDate: DateTime(now.year - 2),
      lastDate: DateTime(now.year + 5),
      initialDate: now,
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
    );
    if (time == null || !mounted) return;
    String two(int n) => n.toString().padLeft(2, '0');
    field.text =
        '${date.year}-${two(date.month)}-${two(date.day)}'
        'T${two(time.hour)}:${two(time.minute)}';
  }

  String? _required(String? value) =>
      value == null || value.trim().isEmpty ? 'Champ requis.' : null;

  Future<void> _submit() async {
    if (!_actorValid ||
        _loading ||
        _submitting ||
        _attempted ||
        !_form.currentState!.validate()) {
      return;
    }
    if (_kind == 'departure' && !_canCreateDeparture) return;
    if (_kind == 'route' &&
        (_origin == null || _destination == null || _origin == _destination)) {
      setState(() => _error = 'Choisissez deux lieux distincts de cet Espace.');
      return;
    }
    if (_kind == 'departure' && _route == null) {
      setState(() => _error = 'Choisissez une route existante.');
      return;
    }
    if (_kind == 'departure' && _publish) {
      final approved = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Publier ce départ ?'),
          content: const Text(
            'Le service Transport vérifiera la route, les dates, '
            'la capacité vendable et le tarif avant publication.',
          ),
          actions: [
            MakoloActionButton(
              label: 'Annuler',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => Navigator.pop(dialogContext, false),
            ),
            MakoloActionButton(
              label: 'Publier',
              appearance: MakoloActionAppearance.primary,
              onPressed: () => Navigator.pop(dialogContext, true),
            ),
          ],
        ),
      );
      if (approved != true || !_actorValid || !mounted) return;
    }
    final epoch = _epoch;
    setState(() {
      _attempted = true;
      _submitting = true;
      _error = null;
    });
    final body = <String, dynamic>{'kind': _kind};
    if (_kind == 'route') {
      body.addAll({
        'origin': _origin,
        'destination': _destination,
        'name': _name.text.trim(),
        'code': _code.text.trim(),
      });
    } else if (_kind == 'vehicle') {
      body.addAll({
        'label': _name.text.trim(),
        'registration': _registration.text.trim(),
        'vehicle_type': _vehicleType,
        'passenger_capacity': _capacity.text.trim(),
      });
    } else {
      body.addAll({
        'route': _route,
        'vehicle': _vehicle,
        'title': _title.text.trim(),
        'timezone': _timezone.text.trim(),
        'start_at': _start.text.trim(),
        'end_at': _end.text.trim(),
        'capacity': _capacity.text.trim(),
        'fare_name': _fareName.text.trim(),
        'unit_price': _price.text.trim(),
        'currency': _currency.text.trim().toUpperCase(),
        'payment_mode': _mode,
        'boarding_instructions': _boarding.text.trim(),
        'operational_reference': _reference.text.trim(),
        'publish': _publish,
      });
    }
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Connexion indisponible');
      final response = await api.post(_path, body: body);
      if (response.statusCode == 400) {
        // A definitive owner validation failure is safe to correct; unknown
        // network results remain retry-locked against duplicate creation.
        if (mounted && _actorValid && epoch == _epoch) {
          setState(() {
            _attempted = false;
            _error =
                'Les valeurs ont été refusées. Vérifiez les lieux, '
                'le fuseau, le prix et les capacités du départ.';
          });
        }
        return;
      }
      if (response.statusCode != 201) {
        throw StateError('Création non confirmée');
      }
      final data = response.jsonObject();
      final space = spaceMap(data['space']);
      final created = spaceMap(data['created']);
      final expectedKind = switch (_kind) {
        'route' => 'transport_route',
        'vehicle' => 'vehicle',
        _ => 'occurrence',
      };
      if (space?['id'] != widget.actor.space.id ||
          space?['slug'] != widget.actor.space.slug ||
          data['responsibility'] != 'all' ||
          created?['id'] is! String ||
          created?['kind'] != expectedKind) {
        throw const FormatException('Réponse propriétaire incohérente');
      }
      if (!mounted || !_actorValid || epoch != _epoch) return;
      context.go(
        '/space/${Uri.encodeComponent(widget.actor.space.slug)}'
        '/retrieval/${Uri.encodeComponent(created!['kind'] as String)}'
        '/${Uri.encodeComponent(created['id'] as String)}',
      );
    } on Object {
      if (mounted && _actorValid && epoch == _epoch) {
        setState(() {
          _error =
              'Résultat non confirmé. Vérifiez la réalité dans Métier '
              'avant de créer une seconde fois.';
        });
      }
    } finally {
      if (mounted && epoch == _epoch) setState(() => _submitting = false);
    }
  }

  Widget _choice(
    String label,
    String? value,
    List<Map<String, dynamic>> items,
    ValueChanged<String?> onChanged, {
    bool optional = false,
  }) => DropdownButtonFormField<String>(
    initialValue: value,
    decoration: InputDecoration(labelText: label),
    items: [
      if (optional)
        const DropdownMenuItem<String>(
          value: '',
          child: Text('Aucun pour le moment'),
        ),
      for (final item in items)
        if (spaceText(item['id']) case final String id)
          DropdownMenuItem(
            value: id,
            child: Text(
              spaceText(item['name']) ?? spaceText(item['label']) ?? id,
            ),
          ),
    ],
    onChanged: _attempted
        ? null
        : (next) => onChanged(next == '' ? null : next),
    validator: optional ? null : _required,
  );

  @override
  Widget build(BuildContext context) {
    final title = switch (_kind) {
      'route' => 'Créer une route',
      'vehicle' => 'Ajouter un véhicule',
      _ => 'Planifier un départ',
    };
    return Scaffold(
      appBar: AppBar(title: const Text('Créer dans Transport')),
      body: !_actorValid
          ? const Center(child: Text('Choisissez votre Espace autorisé.'))
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                if (_loading) const LinearProgressIndicator(),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ),
                if (!_loading)
                  Form(
                    key: _form,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          title,
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                        const SizedBox(height: 12),
                        DropdownButtonFormField<String>(
                          initialValue: _kind,
                          decoration: const InputDecoration(
                            labelText: 'Ce que vous préparez',
                          ),
                          items: [
                            const DropdownMenuItem(
                              value: 'route',
                              child: Text('Route'),
                            ),
                            const DropdownMenuItem(
                              value: 'vehicle',
                              child: Text('Véhicule'),
                            ),
                            if (_canCreateDeparture)
                              const DropdownMenuItem(
                                value: 'departure',
                                child: Text('Départ'),
                              ),
                          ],
                          onChanged: _attempted
                              ? null
                              : (v) {
                                  if (v != null) setState(() => _kind = v);
                                },
                        ),
                        const SizedBox(height: 12),
                        if (_kind == 'route') ...[
                          _choice(
                            'Origine',
                            _origin,
                            _places,
                            (v) => setState(() => _origin = v),
                          ),
                          _choice(
                            'Destination',
                            _destination,
                            _places,
                            (v) => setState(() => _destination = v),
                          ),
                          if (_morePlaces)
                            MakoloActionButton(
                              label: 'Voir davantage de lieux',
                              appearance: MakoloActionAppearance.quiet,
                              onPressed: () => _loadOptions(more: 'places'),
                            ),
                          TextFormField(
                            controller: _name,
                            enabled: !_attempted,
                            decoration: const InputDecoration(
                              labelText: 'Nom de la route (facultatif)',
                            ),
                          ),
                          TextFormField(
                            controller: _code,
                            enabled: !_attempted,
                            decoration: const InputDecoration(
                              labelText: 'Code (facultatif)',
                            ),
                          ),
                        ] else if (_kind == 'vehicle') ...[
                          TextFormField(
                            controller: _name,
                            enabled: !_attempted,
                            decoration: const InputDecoration(
                              labelText: 'Véhicule',
                            ),
                            validator: _required,
                          ),
                          TextFormField(
                            controller: _registration,
                            enabled: !_attempted,
                            decoration: const InputDecoration(
                              labelText: 'Immatriculation (facultative)',
                            ),
                          ),
                          DropdownButtonFormField<String>(
                            initialValue: _vehicleType,
                            decoration: const InputDecoration(
                              labelText: 'Type',
                            ),
                            items: const [
                              DropdownMenuItem(
                                value: 'bus',
                                child: Text('Bus'),
                              ),
                              DropdownMenuItem(
                                value: 'minibus',
                                child: Text('Minibus'),
                              ),
                              DropdownMenuItem(
                                value: 'van',
                                child: Text('Van'),
                              ),
                              DropdownMenuItem(
                                value: 'car',
                                child: Text('Voiture'),
                              ),
                              DropdownMenuItem(
                                value: 'other',
                                child: Text('Autre'),
                              ),
                            ],
                            onChanged: _attempted
                                ? null
                                : (v) =>
                                      setState(() => _vehicleType = v ?? 'bus'),
                          ),
                          TextFormField(
                            controller: _capacity,
                            enabled: !_attempted,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                              labelText: 'Places physiques',
                            ),
                            validator: (v) => (int.tryParse(v ?? '') ?? 0) < 1
                                ? 'Capacité positive requise.'
                                : null,
                          ),
                        ] else ...[
                          if (_routes.isEmpty)
                            const Text('Créez d’abord une route réelle.'),
                          _choice('Route', _route, _routes, (v) {
                            setState(() {
                              _route = v;
                              final matched = _routes.where(
                                (row) => row['id'] == v,
                              );
                              _timezone.text = matched.isEmpty
                                  ? ''
                                  : (spaceText(matched.first['timezone']) ??
                                        '');
                            });
                          }),
                          if (_moreRoutes)
                            MakoloActionButton(
                              label: 'Voir davantage de routes',
                              appearance: MakoloActionAppearance.quiet,
                              onPressed: () => _loadOptions(more: 'routes'),
                            ),
                          _choice(
                            'Véhicule (facultatif)',
                            _vehicle,
                            _vehicles,
                            (v) => setState(() => _vehicle = v),
                            optional: true,
                          ),
                          if (_moreVehicles)
                            MakoloActionButton(
                              label: 'Voir davantage de véhicules',
                              appearance: MakoloActionAppearance.quiet,
                              onPressed: () => _loadOptions(more: 'vehicles'),
                            ),
                          TextFormField(
                            controller: _title,
                            enabled: !_attempted,
                            decoration: const InputDecoration(
                              labelText: 'Nom du service (facultatif)',
                            ),
                          ),
                          TextFormField(
                            controller: _timezone,
                            enabled: !_attempted,
                            decoration: const InputDecoration(
                              labelText: 'Fuseau IANA du départ',
                            ),
                            validator: _required,
                          ),
                          TextFormField(
                            controller: _start,
                            enabled: !_attempted,
                            readOnly: true,
                            onTap: () => _pickDateTime(_start),
                            decoration: const InputDecoration(
                              labelText: 'Date et heure de départ',
                              suffixIcon: Icon(Icons.calendar_today_outlined),
                            ),
                            validator: _required,
                          ),
                          TextFormField(
                            controller: _end,
                            enabled: !_attempted,
                            readOnly: true,
                            onTap: () => _pickDateTime(_end),
                            decoration: const InputDecoration(
                              labelText: 'Arrivée estimée (facultative)',
                              suffixIcon: Icon(Icons.calendar_today_outlined),
                            ),
                          ),
                          TextFormField(
                            controller: _capacity,
                            enabled: !_attempted,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                              labelText: 'Places vendables',
                            ),
                            validator: (v) => (int.tryParse(v ?? '') ?? 0) < 1
                                ? 'Capacité vendable positive requise.'
                                : null,
                          ),
                          TextFormField(
                            controller: _fareName,
                            enabled: !_attempted,
                            decoration: const InputDecoration(
                              labelText: 'Nom du tarif',
                            ),
                          ),
                          TextFormField(
                            controller: _price,
                            enabled: !_attempted,
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                            decoration: const InputDecoration(
                              labelText: 'Prix par place',
                            ),
                            validator: (v) {
                              final amount = double.tryParse(v ?? '');
                              return amount == null || amount < 0
                                  ? 'Prix invalide.'
                                  : null;
                            },
                          ),
                          TextFormField(
                            controller: _currency,
                            enabled: !_attempted,
                            decoration: const InputDecoration(
                              labelText: 'Devise ISO',
                            ),
                            validator: (v) =>
                                RegExp(r'^[A-Za-z]{3}$').hasMatch(v ?? '')
                                ? null
                                : 'Code ISO de trois lettres requis.',
                          ),
                          DropdownButtonFormField<String>(
                            initialValue: _mode,
                            decoration: const InputDecoration(
                              labelText: 'Paiement',
                            ),
                            items: const [
                              DropdownMenuItem(
                                value: 'upfront',
                                child: Text('Avant confirmation'),
                              ),
                              DropdownMenuItem(
                                value: 'on_site',
                                child: Text('Sur place'),
                              ),
                              DropdownMenuItem(
                                value: 'none',
                                child: Text('Sans paiement'),
                              ),
                            ],
                            onChanged: _attempted
                                ? null
                                : (v) => setState(() => _mode = v ?? 'upfront'),
                          ),
                          TextFormField(
                            controller: _boarding,
                            enabled: !_attempted,
                            maxLength: 320,
                            decoration: const InputDecoration(
                              labelText:
                                  'Consignes d’embarquement (facultatives)',
                            ),
                          ),
                          TextFormField(
                            controller: _reference,
                            enabled: !_attempted,
                            maxLength: 80,
                            decoration: const InputDecoration(
                              labelText:
                                  'Référence opérationnelle (facultative)',
                            ),
                          ),
                          CheckboxListTile(
                            value: _publish,
                            title: const Text(
                              'Publier le départ après validation',
                            ),
                            onChanged: _attempted
                                ? null
                                : (v) => setState(() => _publish = v ?? false),
                          ),
                          const Text(
                            'Places physiques, places vendables, réservations '
                            'et présence sont des vérités distinctes.',
                          ),
                        ],
                        const SizedBox(height: 20),
                        MakoloActionButton(
                          label: _submitting
                              ? 'Enregistrement…'
                              : _kind == 'departure' && !_publish
                              ? 'Créer en brouillon'
                              : 'Confirmer la création',
                          appearance: MakoloActionAppearance.primary,
                          busy: _submitting,
                          onPressed:
                              _attempted ||
                                  _submitting ||
                                  _loading ||
                                  (_kind == 'departure' && !_canCreateDeparture)
                              ? null
                              : _submit,
                        ),
                      ],
                    ),
                  ),
                MakoloActionButton(
                  label: 'Retour à Métier',
                  appearance: MakoloActionAppearance.secondary,
                  onPressed: _submitting
                      ? null
                      : () => context.go('/space/work'),
                ),
              ],
            ),
    );
  }
}
