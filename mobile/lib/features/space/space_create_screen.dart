import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';

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
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    if (_saving || _created || !_form.currentState!.validate()) return;
    final repository = widget.runtime.space;
    final actor = widget.runtime.actorContext;
    if (repository?.sync == null || actor == null) {
      setState(() => _error = 'Une connexion est nécessaire pour créer un Espace.');
      return;
    }
    setState(() { _saving = true; _error = null; });
    try {
      final identity = await repository!.createSpace(
        name: _name.text, publicProfile: _publicProfile,
      );
      _created = true;
      // A POST response does not substitute for a current authority inventory.
      await repository.refreshInventory();
      final authorized = (await repository.readInventory()).any(
        (space) => space.identity.id == identity.id &&
            space.identity.slug == identity.slug,
      );
      if (!authorized) {
        throw StateError('L’accès à cet Espace doit être vérifié.');
      }
      await repository.refreshWorkspace(identity);
      await actor.selectSpace(identity);
      if (mounted) context.go('/space/now');
    } on Object {
      if (mounted) {
        setState(() => _error = _created
            ? 'Espace créé. La vérification de votre accès est indisponible. '
              'Revenez à Agir comme après actualisation.'
            : 'La création n’a pas été confirmée. Vérifiez votre connexion avant de réessayer.');
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
                    ? 'Indiquez un nom.' : null,
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                value: _publicProfile,
                onChanged: _saving || _created ? null :
                    (value) => setState(() => _publicProfile = value),
                title: const Text('Présentation publique'),
                subtitle: const Text(
                  'Désactivée par défaut. Les données des membres restent privées.',
                ),
              ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.md),
                  child: Text(
                    _error!,
                    style: TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
                ),
              const SizedBox(height: MakoloSpacing.lg),
              FilledButton(
                onPressed: _saving || _created ? null : _create,
                child: Text(_saving ? 'Création…' : 'Créer cet Espace'),
              ),
              if (_created)
                TextButton(
                  onPressed: () => context.go('/me'),
                  child: const Text('Revenir à Moi'),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
