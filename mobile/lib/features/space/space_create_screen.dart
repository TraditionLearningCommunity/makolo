import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../app/runtime/actor_context.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';

/// Native creation through the canonical Organizations owner contract.
class SpaceCreateScreen extends StatefulWidget {
  const SpaceCreateScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  State<SpaceCreateScreen> createState() => _SpaceCreateScreenState();
}

class _SpaceCreateScreenState extends State<SpaceCreateScreen> {
  static const _draftOwner = 'Organizations';
  static const _draftKind = 'space.creation';
  static const _draftResourceId = 'new';
  static const _draftId = 'space:create';
  Timer? _autosave;
  Future<void> _draftTail = Future<void>.value();
  bool _restoring = true;

  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  bool _publicProfile = true;
  bool _saving = false;
  bool _created = false;
  bool _creationAttempted = false;
  SpaceActorIdentity? _createdIdentity;
  String? _error;

  @override
  void initState() {
    super.initState();
    _name.addListener(_scheduleDraft);
    unawaited(_restoreDraft());
  }

  Future<void> _restoreDraft() async {
    try {
      final draft = await widget.runtime.drafts?.read(
        owner: _draftOwner,
        resourceKind: _draftKind,
        resourceId: _draftResourceId,
      );
      if (!mounted) return;
      final payload = draft?.payload;
      final state = payload?['submission_state'];
      final savedName = payload?['name'];
      final savedPublic = payload?['public_profile'];
      final spaceId = payload?['created_space_id'];
      final spaceSlug = payload?['created_space_slug'];
      final identity =
          spaceId is String &&
              spaceId.isNotEmpty &&
              spaceSlug is String &&
              spaceSlug.isNotEmpty
          ? SpaceActorIdentity(id: spaceId, slug: spaceSlug)
          : null;
      setState(() {
        if (savedName is String) _name.text = savedName;
        if (savedPublic is bool) _publicProfile = savedPublic;
        _creationAttempted =
            state == 'verification_required' || state == 'created_unverified';
        _created = state == 'created_unverified' && identity != null;
        _createdIdentity = identity;
        if (_creationAttempted) {
          _error = _created
              ? 'La création précédente a répondu. Vérifiez votre accès '
                    'avant de continuer.'
              : 'Une demande précédente est incertaine. Vérifiez vos '
                    'Espaces avant toute nouvelle création.';
        }
        _restoring = false;
      });
    } on Object {
      if (mounted) {
        setState(() {
          _restoring = false;
          _error = 'Brouillon local indisponible : réessayez avant de créer.';
        });
      }
    }
  }

  void _scheduleDraft() {
    if (_restoring || _creationAttempted || _saving) return;
    _autosave?.cancel();
    _autosave = Timer(const Duration(milliseconds: 350), () {
      unawaited(_saveDraft(state: 'editing').catchError((Object _) {}));
    });
  }

  /// Serializes local writes so an older autosave cannot overwrite the
  /// durable "request may already have reached the owner" state.
  Future<void> _saveDraft({
    required String state,
    SpaceActorIdentity? created,
  }) {
    final repository = widget.runtime.drafts;
    if (repository == null) {
      return Future<void>.error(
        StateError('Personal local draft store is unavailable'),
      );
    }
    final name = _name.text.trim();
    final publicProfile = _publicProfile;
    final update = _draftTail.then(
      (_) => repository.saveLocal(
        draftId: _draftId,
        owner: _draftOwner,
        resourceKind: _draftKind,
        resourceId: _draftResourceId,
        payload: <String, dynamic>{
          'name': name,
          'public_profile': publicProfile,
          'submission_state': state,
          if (created != null) 'created_space_id': created.id,
          if (created != null) 'created_space_slug': created.slug,
        },
      ),
    );
    _draftTail = update.then<void>(
      (_) {},
      onError: (Object _, StackTrace _) {},
    );
    return update;
  }

  Future<void> _deleteDraft() async {
    _autosave?.cancel();
    await _draftTail;
    await widget.runtime.drafts?.delete(
      owner: _draftOwner,
      resourceKind: _draftKind,
      resourceId: _draftResourceId,
    );
  }

  @override
  void dispose() {
    _autosave?.cancel();
    if (!_creationAttempted && !_created && !_restoring) {
      unawaited(_saveDraft(state: 'editing').catchError((Object _) {}));
    }
    _name.removeListener(_scheduleDraft);
    _name.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    if (_saving ||
        _restoring ||
        _creationAttempted ||
        !_form.currentState!.validate()) {
      return;
    }
    final repository = widget.runtime.space;
    final actor = widget.runtime.actorContext;
    if (repository?.sync == null || actor == null) {
      try {
        await _saveDraft(state: 'editing');
      } on Object {
        // A missing local store is reported separately from connectivity.
      }
      if (mounted) {
        setState(
          () => _error =
              'Brouillon conservé sur cet appareil lorsque le '
              'stockage est disponible. La création nécessite le réseau.',
        );
      }
      return;
    }
    _autosave?.cancel();
    setState(() {
      _saving = true;
      _creationAttempted = true;
      _error = null;
    });
    var requestStarted = false;
    try {
      // Persist BEFORE the first POST: after an ambiguous response, never
      // silently send another Space creation on a cold restart.
      await _saveDraft(state: 'verification_required');
      requestStarted = true;
      final identity = await repository!.createSpace(
        name: _name.text,
        publicProfile: _publicProfile,
      );
      _createdIdentity = identity;
      if (mounted) setState(() => _created = true);
      await _saveDraft(state: 'created_unverified', created: identity);
      // A POST response is not authority. Only the owner inventory and
      // workspace can confirm access to the newly created Space.
      await _verifyCreatedSpace(identity);
      try {
        await _deleteDraft();
      } on Object {
        // Verified authority is not undone by local draft cleanup failure.
      }
      if (mounted) context.go('/space/now');
    } on MakoloApiError catch (error) {
      final denied =
          !_created &&
          const {400, 401, 403, 404, 422}.contains(error.statusCode);
      if (denied) {
        _creationAttempted = false;
        try {
          await _saveDraft(state: 'editing');
        } on Object {
          // Preserve the error state and never claim the draft was saved.
        }
      }
      if (mounted) {
        setState(() {
          _error = _created
              ? 'Espace créé, accès à vérifier. Utilisez « Vérifier mon accès ».'
              : _creationAttempted
              ? 'Réponse incertaine : vérifiez vos Espaces avant toute '
                    'nouvelle demande de création.'
              : 'La création a été refusée. Vérifiez les informations saisies.';
        });
      }
    } on Object {
      if (!requestStarted) _creationAttempted = false;
      if (mounted) {
        setState(() {
          _error = !requestStarted
              ? 'Impossible d’enregistrer le brouillon local. '
                    'La demande de création n’a pas été envoyée.'
              : _created
              ? 'Espace créé, accès à vérifier. Utilisez « Vérifier mon accès ».'
              : 'Réponse incertaine : vérifiez vos Espaces avant '
                    'de créer à nouveau.';
        });
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _unlockAfterManualVerification() async {
    if (_saving || !_creationAttempted || _created) return;
    final proceed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reprendre le brouillon ?'),
        content: const Text(
          'Consultez d’abord vos Espaces. Une demande précédente a pu '
          'aboutir malgré l’absence de réponse. En réessayant, vous '
          'pourriez créer un doublon. Confirmez seulement après avoir '
          'effectué cette vérification.',
        ),
        actions: [
          MakoloActionButton(
            label: 'Annuler',
            onPressed: () => Navigator.of(context).pop(false),
            appearance: MakoloActionAppearance.quiet,
          ),
          MakoloActionButton(
            label: 'J’ai vérifié mes Espaces',
            onPressed: () => Navigator.of(context).pop(true),
            appearance: MakoloActionAppearance.primary,
          ),
        ],
      ),
    );
    if (proceed != true || !mounted) return;
    try {
      await _saveDraft(state: 'editing');
      if (mounted) {
        setState(() {
          _creationAttempted = false;
          _error = null;
        });
      }
    } on Object {
      if (mounted) {
        setState(
          () => _error = 'La préparation locale n’a pas pu être réouverte.',
        );
      }
    }
  }

  Future<void> _verifyCreatedSpace(SpaceActorIdentity identity) async {
    final repository = widget.runtime.space!;
    final actor = widget.runtime.actorContext!;
    await repository.refreshInventory();
    final state = await repository.readSource(repository.inventorySource());
    if (state.lastSuccessAt == null ||
        state.invalidated ||
        state.lastErrorCode != null) {
      throw StateError('Inventaire non vérifié.');
    }
    final authorized = (await repository.readInventory()).any(
      (space) =>
          space.identity.id == identity.id &&
          space.identity.slug == identity.slug,
    );
    if (!authorized) {
      throw StateError('L’accès à cet Espace doit être vérifié.');
    }
    await repository.refreshWorkspace(identity);
    final verified = await repository.readSource(
      repository.workspaceSource(identity),
    );
    if (verified.lastSuccessAt == null ||
        verified.invalidated ||
        verified.lastErrorCode != null) {
      throw StateError('Autorité non vérifiée.');
    }
    await actor.selectSpace(identity);
  }

  Future<void> _retryVerification() async {
    if (_saving) return;
    final identity = _createdIdentity;
    if (identity == null) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await _verifyCreatedSpace(identity);
      try {
        await _deleteDraft();
      } on Object {
        // Access was already verified by the canonical owner.
      }
      if (mounted) context.go('/space/now');
    } on Object {
      if (mounted) {
        setState(
          () => _error = 'La vérification reste indisponible. Aucun accès n’a été accordé.',
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Créer un Espace')),
      body: SafeArea(
        child: Form(
          key: _form,
          child: ListView(
            padding: const EdgeInsets.all(MakoloSpacing.inner),
            children: [
              Text(
                'Créez l’Espace de votre entreprise, association, école ou collectif.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: MakoloSpacing.lg),
              TextFormField(
                enabled: !_saving && !_creationAttempted,
                controller: _name,
                maxLength: 180,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(labelText: 'Nom de l’Espace'),
                validator: (value) => value == null || value.trim().isEmpty
                    ? 'Indiquez un nom.'
                    : null,
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                value: _publicProfile,
                onChanged: _saving || _created || _creationAttempted
                    ? null
                    : (value) {
                        setState(() => _publicProfile = value);
                        _scheduleDraft();
                      },
                title: const Text('Présentation publique'),
                subtitle: Text(
                  _publicProfile
                      ? 'La présentation de cet Espace est visible par tous. '
                            'Les informations privées des membres ne sont pas '
                            'publiées.'
                      : 'La présentation de cet Espace n’est pas publique.',
                ),
              ),
              if (!_restoring)
                const Padding(
                  padding: EdgeInsets.only(top: MakoloSpacing.sm),
                  child: Text(
                    'Votre préparation reste sur cet appareil. '
                    'La création effective exige une réponse du propriétaire.',
                  ),
                ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.symmetric(
                    vertical: MakoloSpacing.md,
                  ),
                  child: Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              const SizedBox(height: MakoloSpacing.lg),
              MakoloActionButton(
                label: _saving ? 'Création…' : 'Créer cet Espace',
                onPressed: _saving || _restoring || _creationAttempted
                    ? null
                    : _create,
                appearance: MakoloActionAppearance.primary,
              ),
              if (_creationAttempted && !_created) ...[
                MakoloActionButton(
                  label: 'Consulter mes Espaces depuis Moi',
                  onPressed: () => context.go('/me'),
                  appearance: MakoloActionAppearance.quiet,
                ),
                MakoloActionButton(
                  label: 'Après vérification, reprendre le brouillon',
                  onPressed: _saving ? null : _unlockAfterManualVerification,
                  appearance: MakoloActionAppearance.secondary,
                ),
              ],
              if (_created) ...[
                MakoloActionButton(
                  label: 'Vérifier mon accès',
                  onPressed: _saving ? null : _retryVerification,
                  appearance: MakoloActionAppearance.secondary,
                ),
                MakoloActionButton(
                  label: 'Revenir à Moi',
                  onPressed: () => context.go('/me'),
                  appearance: MakoloActionAppearance.quiet,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
