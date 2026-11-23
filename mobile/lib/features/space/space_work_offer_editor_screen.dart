import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../presentation/contracts/space_presentation.dart';

/// MT5 Commerce authoring. The backend validates current Space, Activity
/// Commerce permission and the actual Offer owner before every operation.
class SpaceWorkOfferEditorScreen extends StatefulWidget {
  const SpaceWorkOfferEditorScreen({
    super.key,
    required this.runtime,
    required this.actor,
    this.activityId,
    this.offerId,
  }) : assert((activityId == null) != (offerId == null));

  final AppRuntime runtime;
  final SpaceActorContext actor;
  final String? activityId;
  final String? offerId;

  @override
  State<SpaceWorkOfferEditorScreen> createState() =>
      _SpaceWorkOfferEditorScreenState();
}

class _SpaceWorkOfferEditorScreenState
    extends State<SpaceWorkOfferEditorScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _description = TextEditingController();
  final _price = TextEditingController(text: '0.00');
  final _currency = TextEditingController(text: 'USD');
  final _minimum = TextEditingController(text: '1');
  final _maximum = TextEditingController();
  List<(String, String)> _modes = const [];
  List<(String, String)> _statuses = const [];
  String? _mode;
  String? _status;
  bool _loading = true;
  bool _posting = false;
  bool _attempted = false;
  String? _error;
  int _epoch = 0;

  bool get _actorValid => widget.runtime.actorContext?.value == widget.actor;
  bool get _editing => widget.offerId != null;

  String get _ownerPath {
    final slug = Uri.encodeComponent(widget.actor.space.slug);
    final id = Uri.encodeComponent(widget.offerId ?? widget.activityId!);
    final tail = _editing ? 'offers/$id/' : 'activities/$id/offers/';
    return Uri(
      path: 'api/v1/organizations/workspaces/$slug/work/g3/$tail',
      queryParameters: widget.actor.perspective.isAll
          ? null
          : {'responsibility': widget.actor.perspective.id!},
    ).toString();
  }

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_onActorChanged);
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant SpaceWorkOfferEditorScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      widget.runtime.actorContext?.addListener(_onActorChanged);
    }
    if (oldWidget.actor != widget.actor ||
        oldWidget.activityId != widget.activityId ||
        oldWidget.offerId != widget.offerId ||
        oldWidget.runtime != widget.runtime) {
      _onActorChanged();
    }
  }

  @override
  void dispose() {
    ++_epoch;
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    for (final controller in [
      _name,
      _description,
      _price,
      _currency,
      _minimum,
      _maximum,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  void _onActorChanged() {
    ++_epoch;
    if (!mounted) return;
    setState(() {
      _loading = _actorValid;
      _attempted = false;
      _error = null;
      _modes = const [];
      _statuses = const [];
    });
    if (_actorValid) unawaited(_load());
  }

  List<(String, String)> _choices(dynamic raw) {
    if (raw is! List) return const [];
    return [
      for (final choice in raw)
        if (choice is List &&
            choice.length == 2 &&
            choice[0] is String &&
            choice[1] is String)
          (choice[0] as String, choice[1] as String),
    ];
  }

  Future<void> _load() async {
    if (!_actorValid) return;
    final epoch = ++_epoch;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Connexion indisponible');
      final result = await api.get(_ownerPath);
      if (result.statusCode != 200) throw StateError('Offre inaccessible');
      final data = result.jsonObject();
      final space = spaceMap(data['space']);
      final activity = spaceMap(data['activity']);
      final offer = spaceMap(data['offer']);
      if (space?['id'] != widget.actor.space.id ||
          space?['slug'] != widget.actor.space.slug ||
          data['responsibility'] != (widget.actor.perspective.id ?? 'all') ||
          activity?['kind'] != 'activity' ||
          (widget.activityId != null && activity?['id'] != widget.activityId) ||
          (widget.offerId != null &&
              (offer?['kind'] != 'offer' || offer?['id'] != widget.offerId))) {
        throw const FormatException('Offer owner mismatch');
      }
      final options = spaceMap(data['options']);
      final paymentModes = _choices(options?['payment_modes']);
      final statuses = _choices(options?['statuses']);
      if (paymentModes.isEmpty) throw const FormatException('Modes absents');
      if (!mounted || epoch != _epoch || !_actorValid) return;
      _name.text = spaceText(offer?['name']) ?? '';
      _description.text = spaceText(offer?['description']) ?? '';
      _price.text = spaceText(offer?['unit_price']) ?? '0.00';
      _currency.text = spaceText(offer?['currency']) ?? 'USD';
      _minimum.text = '${offer?['min_quantity'] ?? 1}';
      _maximum.text = offer?['max_quantity']?.toString() ?? '';
      setState(() {
        _modes = paymentModes;
        _statuses = statuses.where((row) => row.$1.isNotEmpty).toList();
        _mode = spaceText(offer?['payment_mode']) ?? 'none';
        _status = spaceText(offer?['status']) ?? 'draft';
      });
    } on Object {
      if (!mounted || epoch != _epoch || !_actorValid) return;
      setState(() {
        _error =
            'Cette Offre n’est plus accessible dans ce contexte. '
            'Vérifiez vos droits et votre connexion.';
      });
    } finally {
      if (mounted && epoch == _epoch) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _submit() async {
    if (!_actorValid ||
        _loading ||
        _posting ||
        _attempted ||
        !_formKey.currentState!.validate()) {
      return;
    }
    final epoch = _epoch;
    setState(() {
      _attempted = true;
      _posting = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Connexion indisponible');
      final response = await api.post(
        _ownerPath,
        body: {
          'name': _name.text.trim(),
          'description': _description.text.trim(),
          'unit_price': _price.text.trim(),
          'currency': _currency.text.trim().toUpperCase(),
          'payment_mode': _mode,
          'min_quantity': _minimum.text.trim(),
          'max_quantity': _maximum.text.trim(),
          if (_editing) 'status': _status,
        },
      );
      if (response.statusCode == 400) {
        // The owner rejected the command before committing. Allow the user
        // to repair the form; this is not an ambiguous network outcome.
        if (mounted && _actorValid && epoch == _epoch) {
          setState(() {
            _attempted = false;
            _error =
                'Impossible d’enregistrer l’offre. Vérifiez le prix, '
                'le mode de paiement et les quantités.';
          });
        }
        return;
      }
      if (response.statusCode != (_editing ? 200 : 201)) {
        throw StateError('Enregistrement non confirmé');
      }
      final result = response.jsonObject();
      final space = spaceMap(result['space']);
      final offer = spaceMap(result['offer']);
      if (space?['id'] != widget.actor.space.id ||
          result['responsibility'] != (widget.actor.perspective.id ?? 'all') ||
          offer?['kind'] != 'offer' ||
          offer?['id'] is! String ||
          (_editing && offer?['id'] != widget.offerId)) {
        throw const FormatException('Réponse Offer incohérente');
      }
      if (!mounted || !_actorValid || epoch != _epoch) return;
      context.go(
        '/space/${Uri.encodeComponent(widget.actor.space.slug)}'
        '/retrieval/offer/${Uri.encodeComponent(offer!['id'] as String)}',
      );
    } on Object {
      if (mounted && _actorValid && epoch == _epoch) {
        setState(() {
          _error =
              'Résultat non confirmé. Vérifiez l’offre dans Métier '
              'avant de renouveler une action pour éviter un doublon.';
        });
      }
    } finally {
      if (mounted && epoch == _epoch) setState(() => _posting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = _editing ? 'Modifier l’offre' : 'Nouvelle offre';
    return Scaffold(
      appBar: AppBar(title: Text(title)),
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
                if (!_loading && _modes.isNotEmpty)
                  Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          title,
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _name,
                          enabled: !_attempted,
                          maxLength: 180,
                          decoration: const InputDecoration(
                            labelText: 'Nom de l’offre',
                          ),
                          validator: (v) => v == null || v.trim().isEmpty
                              ? 'Donnez un nom à l’offre.'
                              : null,
                        ),
                        TextFormField(
                          controller: _description,
                          enabled: !_attempted,
                          minLines: 2,
                          maxLines: 5,
                          decoration: const InputDecoration(
                            labelText: 'Description',
                          ),
                        ),
                        TextFormField(
                          controller: _price,
                          enabled: !_attempted,
                          keyboardType: const TextInputType.numberWithOptions(
                            decimal: true,
                          ),
                          decoration: const InputDecoration(
                            labelText: 'Prix unitaire',
                          ),
                          validator: (v) {
                            final price = double.tryParse(
                              (v ?? '').trim().replaceAll(',', '.'),
                            );
                            if (price == null || price < 0) {
                              return 'Saisissez un montant valide.';
                            }
                            return null;
                          },
                        ),
                        TextFormField(
                          controller: _currency,
                          enabled: !_attempted,
                          maxLength: 3,
                          decoration: const InputDecoration(
                            labelText: 'Devise ISO (ex. USD)',
                          ),
                          validator: (v) =>
                              RegExp(r'^[A-Za-z]{3}$').hasMatch(v?.trim() ?? '')
                              ? null
                              : 'Code à trois lettres requis.',
                        ),
                        TextFormField(
                          controller: _minimum,
                          enabled: !_attempted,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                            labelText: 'Quantité minimum',
                          ),
                          validator: (v) => (int.tryParse(v ?? '') ?? 0) < 1
                              ? 'Indiquez un minimum positif.'
                              : null,
                        ),
                        TextFormField(
                          controller: _maximum,
                          enabled: !_attempted,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                            labelText: 'Quantité maximum (facultative)',
                          ),
                          validator: (v) {
                            if (v == null || v.trim().isEmpty) return null;
                            final max = int.tryParse(v.trim());
                            if (max == null ||
                                max < (int.tryParse(_minimum.text) ?? 1)) {
                              return 'Maximum inférieur au minimum.';
                            }
                            return null;
                          },
                        ),
                        DropdownButtonFormField<String>(
                          initialValue: _mode,
                          decoration: const InputDecoration(
                            labelText: 'Mode de paiement',
                          ),
                          items: [
                            for (final (value, label) in _modes)
                              DropdownMenuItem(
                                value: value,
                                child: Text(label),
                              ),
                          ],
                          onChanged: _attempted
                              ? null
                              : (v) => setState(() => _mode = v),
                        ),
                        if (_editing)
                          DropdownButtonFormField<String>(
                            initialValue: _status,
                            decoration: const InputDecoration(
                              labelText: 'État de l’offre',
                            ),
                            items: [
                              for (final (value, label) in _statuses)
                                DropdownMenuItem(
                                  value: value,
                                  child: Text(label),
                                ),
                            ],
                            onChanged: _attempted
                                ? null
                                : (v) => setState(() => _status = v),
                          ),
                        const SizedBox(height: 20),
                        MakoloActionButton(
                          label: _posting
                              ? 'Enregistrement…'
                              : _editing
                              ? 'Enregistrer'
                              : 'Créer en brouillon',
                          appearance: MakoloActionAppearance.primary,
                          busy: _posting,
                          onPressed: _attempted || _posting ? null : _submit,
                        ),
                      ],
                    ),
                  ),
                if (!_loading && _modes.isEmpty)
                  MakoloActionButton(
                    label: 'Vérifier les droits et actualiser',
                    appearance: MakoloActionAppearance.quiet,
                    onPressed: _attempted ? null : _load,
                  ),
                MakoloActionButton(
                  label: 'Retour à Métier',
                  appearance: MakoloActionAppearance.secondary,
                  onPressed: _posting ? null : () => context.go('/space/work'),
                ),
              ],
            ),
    );
  }
}
