import 'package:flutter/material.dart';
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
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  bool _publicProfile = false;
  bool _saving = false;
  bool _created = false;
  bool _creationAttempted = false;
  SpaceActorIdentity? _createdIdentity;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    if (_saving || _creationAttempted || !_form.currentState!.validate()) {
      return;
    }
    final repository = widget.runtime.space;
    final actor = widget.runtime.actorContext;
    if (repository?.sync == null || actor == null) {
      setState(
        () => _error = 'Une connexion est nécessaire pour créer un Espace.',
      );
      return;
    }
    setState(() {
      _saving = true;
      _creationAttempted = true;
      _error = null;
    });
    try {
      final identity = await repository!.createSpace(
        name: _name.text,
        publicProfile: _publicProfile,
      );
      _createdIdentity = identity;
      if (mounted) setState(() => _created = true);
      // A POST response does not substitute for a current authority inventory.
      await _verifyCreatedSpace(identity);
      if (mounted) context.go('/space/now');
    } on MakoloApiError catch (error) {
      if (mounted) {
        setState(() {
          if (!_created &&
              const {400, 401, 403, 404, 422}.contains(error.statusCode)) {
            // Only definitive rejections permit editing and resubmitting.
            // Timeouts and conflicts may have followed a successful POST.
            _creationAttempted = false;
          }
          _error = _created
              ? 'Espace créé, accès à vérifier. Utilisez « Vérifier mon accès ».'
              : _creationAttempted
              ? 'Réponse incertaine : vérifiez d’abord vos Espaces '
                    'avant toute nouvelle demande de création.'
              : 'La création a été refusée. Vérifiez les informations saisies.';
        });
      }
    } on Object {
      if (mounted) {
        setState(() {
          _error = _created
              ? 'Espace créé, accès à vérifier. Utilisez « Vérifier mon accès ».'
              : 'Réponse incertaine : la demande a peut-être abouti. '
                    'Consultez vos Espaces avant de créer à nouveau.';
        });
      }
    } finally {
      if (mounted) setState(() => _saving = false);
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
      if (mounted) context.go('/space/now');
    } on Object {
      if (mounted)
        setState(
          () => _error = 'La vérification reste indisponible. Aucun accès n’a été accordé.',
        );
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
                'Pour une entreprise, association, école ou autre collectif.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: MakoloSpacing.lg),
              TextFormField(
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
                onChanged: _saving || _created
                    ? null
                    : (value) => setState(() => _publicProfile = value),
                title: const Text('Présentation publique'),
                subtitle: const Text(
                  'Désactivée par défaut. Les données des membres restent privées.',
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
              FilledButton(
                onPressed: _saving || _creationAttempted ? null : _create,
                child: Text(_saving ? 'Création…' : 'Créer cet Espace'),
              ),
              if (_creationAttempted && !_created)
                TextButton(
                  onPressed: () => context.go('/me'),
                  child: const Text('Consulter mes Espaces depuis Moi'),
                ),
              if (_created) ...[
                OutlinedButton(
                  onPressed: _saving ? null : _retryVerification,
                  child: const Text('Vérifier mon accès'),
                ),
                TextButton(
                  onPressed: () => context.go('/me'),
                  child: const Text('Revenir à Moi'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
