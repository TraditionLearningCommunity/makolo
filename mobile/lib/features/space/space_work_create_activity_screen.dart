import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';

/// G1 creation uses Activity's server owner, not an offline/local new model.
/// Once sent, an ambiguous network result must not silently issue a duplicate.
class SpaceWorkCreateActivityScreen extends StatefulWidget {
  const SpaceWorkCreateActivityScreen({
    super.key,
    required this.runtime,
    required this.actor,
    required this.isCommunity,
    this.archetype,
  });

  final AppRuntime runtime;
  final SpaceActorContext actor;
  final bool isCommunity;

  /// Only affects the visible grammar; the server rechecks the Space owner.
  final String? archetype;

  @override
  State<SpaceWorkCreateActivityScreen> createState() =>
      _SpaceWorkCreateActivityScreenState();
}

class _SpaceWorkCreateActivityScreenState
    extends State<SpaceWorkCreateActivityScreen> {
  final _form = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _shortDescription = TextEditingController();
  final _description = TextEditingController();
  String _visibility = 'private';
  String? _serviceKind;
  bool _sending = false;
  bool _attempted = false;
  bool _confirmed = false;
  String? _error;

  bool get _actorValid => widget.runtime.actorContext?.value == widget.actor;

  String get _archetype =>
      widget.archetype ?? (widget.isCommunity ? 'community' : 'generic');

  bool get _isService => _archetype == 'service_provider';
  bool get _isG2 => _archetype == 'education' || _isService;

  String get _subject => switch (_archetype) {
    'community' => 'initiative',
    'education' => 'programme',
    'service_provider' => 'prestation',
    'creative' => 'création',
    'media' => 'production',
    _ => 'activité',
  };

  @override
  void dispose() {
    _title.dispose();
    _shortDescription.dispose();
    _description.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    if (_sending ||
        _attempted ||
        !_actorValid ||
        !_form.currentState!.validate()) {
      return;
    }
    setState(() {
      _sending = true;
      _attempted = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Connexion absente');
      final slug = Uri.encodeComponent(widget.actor.space.slug);
      final response = await api.post(
        _isG2
            ? 'api/v1/organizations/workspaces/$slug/work/g2/create/'
            : 'api/v1/organizations/workspaces/$slug/work/activities/',
        body: {
          'title': _title.text.trim(),
          'short_description': _shortDescription.text.trim(),
          'description': _description.text.trim(),
          'visibility': _visibility,
          if (_isService) 'service_kind': _serviceKind,
        },
      );
      if (response.statusCode != 201) {
        throw StateError('Création non confirmée');
      }
      final data = response.jsonObject();
      final space = data['space'];
      final activity = data['activity'];
      if (space is! Map ||
          activity is! Map ||
          space['id'] != widget.actor.space.id ||
          space['slug'] != widget.actor.space.slug ||
          activity['id'] is! String ||
          activity['status'] != 'draft' ||
          (_isService && data['service'] is! Map) ||
          (_archetype == 'education' && data['service'] != null)) {
        throw const FormatException('Réponse propriétaire incohérente');
      }
      if (!mounted || !_actorValid) return;
      setState(() => _confirmed = true);
      await _refreshOwnerWork();
      if (mounted && _actorValid) context.go('/space/work');
    } on Object {
      if (mounted && _actorValid) {
        setState(() {
          _error = _confirmed
              ? 'Brouillon créé. Impossible d’actualiser Métier. '
                    'Vérifiez la liste avant de créer à nouveau.'
              : 'La création n’a pas été confirmée. Vérifiez le travail '
                    'de cet Espace avant toute nouvelle tentative, '
                    'pour éviter un doublon.';
        });
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _refreshOwnerWork() async {
    if (!_actorValid) return;
    final repository = widget.runtime.space;
    if (repository == null) throw StateError('Dépôt local absent');
    await repository.refreshWork(widget.actor.space, widget.actor.perspective);
  }

  Future<void> _verifyWithoutCreating() async {
    if (_sending || !_actorValid) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await _refreshOwnerWork();
      if (mounted && _actorValid) context.go('/space/work');
    } on Object {
      if (mounted && _actorValid) {
        setState(() {
          _error =
              'Impossible d’actualiser Métier. '
              'Aucun nouveau brouillon n’a été créé.';
        });
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final label = 'Nouveau${_subject == 'programme' ? '' : 'lle'} $_subject';
    return Scaffold(
      appBar: AppBar(title: Text(label)),
      body: !_actorValid
          ? const Center(child: Text('Sélectionnez votre Espace autorisé.'))
          : SafeArea(
              child: Form(
                key: _form,
                child: ListView(
                  padding: const EdgeInsets.all(MakoloSpacing.lg),
                  children: [
                    Text(
                      label,
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      'Un brouillon sera créé pour cet Espace uniquement '
                      'si vos droits et ses capacités le permettent encore.',
                    ),
                    const SizedBox(height: MakoloSpacing.lg),
                    TextFormField(
                      controller: _title,
                      enabled: !_attempted,
                      maxLength: 220,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: InputDecoration(
                        labelText: 'Nom de l’$_subject',
                      ),
                      validator: (value) => (value?.trim().isEmpty ?? true)
                          ? 'Indiquez un nom.'
                          : null,
                    ),
                    const SizedBox(height: MakoloSpacing.md),
                    TextFormField(
                      controller: _shortDescription,
                      enabled: !_attempted,
                      maxLength: 320,
                      maxLines: 2,
                      decoration: const InputDecoration(
                        labelText: 'En quelques mots',
                      ),
                    ),
                    const SizedBox(height: MakoloSpacing.md),
                    TextFormField(
                      controller: _description,
                      enabled: !_attempted,
                      minLines: 3,
                      maxLines: 6,
                      decoration: const InputDecoration(
                        labelText: 'Description (facultative)',
                      ),
                    ),
                    if (_isService) ...[
                      const SizedBox(height: MakoloSpacing.md),
                      DropdownButtonFormField<String>(
                        initialValue: _serviceKind,
                        decoration: const InputDecoration(
                          labelText: 'Type de prestation',
                        ),
                        items: const [
                          DropdownMenuItem(
                            value: 'application_support',
                            child: Text('Accompagnement de candidature'),
                          ),
                          DropdownMenuItem(
                            value: 'career_support',
                            child: Text('Accompagnement carrière'),
                          ),
                          DropdownMenuItem(
                            value: 'education_guidance',
                            child: Text('Orientation éducative'),
                          ),
                          DropdownMenuItem(
                            value: 'document_support',
                            child: Text('Accompagnement documentaire'),
                          ),
                          DropdownMenuItem(
                            value: 'administrative_support',
                            child: Text('Accompagnement administratif'),
                          ),
                          DropdownMenuItem(
                            value: 'interview_preparation',
                            child: Text('Préparation d’entretien'),
                          ),
                          DropdownMenuItem(
                            value: 'orientation',
                            child: Text('Orientation'),
                          ),
                          DropdownMenuItem(
                            value: 'other',
                            child: Text('Autre'),
                          ),
                        ],
                        validator: (v) => v == null
                            ? 'Choisissez le type de prestation.'
                            : null,
                        onChanged: _attempted
                            ? null
                            : (v) => setState(() => _serviceKind = v),
                      ),
                    ],
                    const SizedBox(height: MakoloSpacing.md),
                    DropdownButtonFormField<String>(
                      initialValue: _visibility,
                      decoration: const InputDecoration(
                        labelText: 'Visibilité',
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'private',
                          child: Text('Privée'),
                        ),
                        DropdownMenuItem(
                          value: 'unlisted',
                          child: Text('Non répertoriée'),
                        ),
                        DropdownMenuItem(
                          value: 'public',
                          child: Text('Publique'),
                        ),
                      ],
                      onChanged: _attempted
                          ? null
                          : (value) {
                              if (value != null) {
                                setState(() => _visibility = value);
                              }
                            },
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: MakoloSpacing.lg),
                      Text(
                        _error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ],
                    const SizedBox(height: MakoloSpacing.lg),
                    if (!_attempted)
                      MakoloActionButton(
                        label: _sending
                            ? 'Envoi en cours…'
                            : 'Créer en brouillon',
                        appearance: MakoloActionAppearance.primary,
                        busy: _sending,
                        onPressed: _sending ? null : _create,
                      ),
                    if (_attempted)
                      MakoloActionButton(
                        label: _sending
                            ? 'Vérification…'
                            : 'Vérifier dans Métier',
                        appearance: MakoloActionAppearance.primary,
                        busy: _sending,
                        onPressed: _sending ? null : _verifyWithoutCreating,
                      ),
                    const SizedBox(height: MakoloSpacing.sm),
                    MakoloActionButton(
                      label: 'Retour à Métier',
                      appearance: MakoloActionAppearance.secondary,
                      onPressed: _sending
                          ? null
                          : () => context.go('/space/work'),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
