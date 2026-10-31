import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';

/// Institutional details remain an authorized server mutation, never an
/// offline permission inferred from a cached TeamMembership or identity.
class SpaceUsSettingsScreen extends StatefulWidget {
  const SpaceUsSettingsScreen({
    super.key,
    required this.runtime,
    required this.slug,
  });

  final AppRuntime runtime;
  final String slug;

  @override
  State<SpaceUsSettingsScreen> createState() => _SpaceUsSettingsScreenState();
}

class _SpaceUsSettingsScreenState extends State<SpaceUsSettingsScreen> {
  final form = GlobalKey<FormState>();
  final name = TextEditingController();
  final description = TextEditingController();
  final website = TextEditingController();
  final email = TextEditingController();
  final phone = TextEditingController();
  bool publicProfile = false;
  bool loading = true;
  bool saving = false;
  bool authorized = false;
  String? error;
  String? loadedSpaceId;

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(onActorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => unawaited(load()));
  }

  void onActorChanged() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(onActorChanged);
    name.dispose();
    description.dispose();
    website.dispose();
    email.dispose();
    phone.dispose();
    super.dispose();
  }

  SpaceActorContext? get actor {
    final context = widget.runtime.actorContext?.value;
    if (context is SpaceActorContext && context.space.slug == widget.slug) {
      return context;
    }
    return null;
  }

  String get usPath => 'api/v1/organizations/workspaces/' +
      Uri.encodeComponent(widget.slug) + '/us/';

  Future<void> load() async {
    final current = actor;
    final api = widget.runtime.api;
    if (current == null || api == null) {
      if (mounted) setState(() { loading = false; authorized = false; });
      return;
    }
    final expectedId = current.space.id;
    setState(() { loading = true; error = null; authorized = false; });
    try {
      final response = await api.get(usPath);
      final payload = response.jsonObject();
      final identity = payload['identity'];
      final caps = payload['capabilities'];
      if (identity is! Map || caps is! Map ||
          identity['id']?.toString() != expectedId ||
          caps['update_space'] != true) {
        throw const FormatException('Settings not available for this actor');
      }
      if (!mounted || actor?.space.id != expectedId) return;
      name.text = identity['name']?.toString() ?? '';
      description.text = identity['description']?.toString() ?? '';
      website.text = identity['website']?.toString() ?? '';
      email.text = identity['contact_email']?.toString() ?? '';
      phone.text = identity['contact_phone']?.toString() ?? '';
      setState(() {
        publicProfile = identity['public_profile'] == true;
        authorized = true;
        loading = false;
        loadedSpaceId = expectedId;
      });
    } on Object {
      if (!mounted || actor?.space.id != expectedId) return;
      setState(() {
        loading = false;
        authorized = false;
        error = 'Impossible de vérifier les droits et les informations '
            'actuelles. Reconnectez-vous puis réessayez.';
      });
    }
  }

  Future<void> save() async {
    final current = actor;
    final api = widget.runtime.api;
    if (!authorized || saving || current == null || api == null ||
        current.space.id != loadedSpaceId ||
        form.currentState?.validate() != true) return;
    final expectedId = current.space.id;
    setState(() { saving = true; error = null; });
    try {
      // No local mutation: the server checks SPACE_MANAGE at PATCH time.
      await api.patch(
        'api/v1/organizations/workspaces/' +
          Uri.encodeComponent(widget.slug) + '/',
        body: {
          'name': name.text.trim(),
          'description': description.text.trim(),
          'website': website.text.trim(),
          'contact_email': email.text.trim(),
          'contact_phone': phone.text.trim(),
          'public_profile': publicProfile,
        },
      );
      if (!mounted || actor?.space.id != expectedId) return;
      final repository = widget.runtime.space;
      if (repository != null) {
        try {
          await repository.refreshUs(current.space);
          await repository.refreshWorkspace(current.space);
        } on Object {
          // Mutation was committed on the server. Do not pretend the cache
          // was refreshed; next visit will reconcile the projection.
        }
      }
      if (!mounted || actor?.space.id != expectedId) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Informations enregistrées.')),
      );
      await load();
    } on MakoloApiError catch (failure) {
      if (!mounted || actor?.space.id != expectedId) return;
      if (failure.statusCode == 401 || failure.statusCode == 403 ||
          failure.statusCode == 404) {
        setState(() {
          authorized = false;
          error = 'Votre autorité a changé. Cet espace ne peut plus être modifié.';
        });
      } else {
        setState(() { error = failure.message; });
      }
    } on Object {
      if (!mounted || actor?.space.id != expectedId) return;
      setState(() {
        error = 'Enregistrement indisponible. '
            'Aucun changement local n’a été considéré comme confirmé.';
      });
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = actor;
    return Scaffold(
      appBar: AppBar(title: const Text('Identité du Space')),
      body: current == null
          ? const Center(
              child: Text('Sélectionnez le Space autorisé pour le modifier.'),
            )
          : loading
              ? const Center(child: CircularProgressIndicator())
              : !authorized
                  ? ListView(
                      padding: const EdgeInsets.all(MakoloSpacing.lg),
                      children: [
                        Text(error ?? 'Cette modification est indisponible.'),
                        TextButton.icon(
                          onPressed: load,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Réessayer'),
                        ),
                      ],
                    )
                  : Form(
                      key: form,
                      child: ListView(
                        padding: const EdgeInsets.all(MakoloSpacing.lg),
                        children: [
                          Text('Informations collectives',
                            style: Theme.of(context).textTheme.titleLarge),
                          const SizedBox(height: MakoloSpacing.sm),
                          const Text('Ces changements engagent le Space. '
                            'Le serveur vérifie votre autorité à chaque enregistrement.'),
                          const SizedBox(height: MakoloSpacing.lg),
                          TextFormField(
                            controller: name,
                            maxLength: 180,
                            decoration: const InputDecoration(labelText: 'Nom du Space'),
                            validator: (v) => (v?.trim().isEmpty ?? true)
                                ? 'Le nom est nécessaire.' : null,
                          ),
                          TextFormField(
                            controller: description,
                            maxLines: 4,
                            decoration: const InputDecoration(labelText: 'Présentation'),
                          ),
                          TextFormField(
                            controller: website,
                            keyboardType: TextInputType.url,
                            decoration: const InputDecoration(labelText: 'Site web'),
                          ),
                          TextFormField(
                            controller: email,
                            keyboardType: TextInputType.emailAddress,
                            decoration: const InputDecoration(labelText: 'Contact général'),
                          ),
                          TextFormField(
                            controller: phone,
                            keyboardType: TextInputType.phone,
                            decoration: const InputDecoration(labelText: 'Téléphone général'),
                          ),
                          SwitchListTile.adaptive(
                            contentPadding: EdgeInsets.zero,
                            title: const Text('Profil public'),
                            subtitle: const Text(
                              'Autoriser la présence publique prévue par le Space. '
                              'Les règles de découverte restent distinctes.',
                            ),
                            value: publicProfile,
                            onChanged: saving
                                ? null : (value) => setState(() => publicProfile = value),
                          ),
                          if (error != null) ...[
                            const SizedBox(height: MakoloSpacing.sm),
                            Text(error!, style: TextStyle(
                              color: Theme.of(context).colorScheme.error)),
                          ],
                          const SizedBox(height: MakoloSpacing.md),
                          FilledButton.icon(
                            onPressed: saving ? null : save,
                            icon: saving
                                ? const SizedBox(
                                    height: 16, width: 16,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Icon(Icons.save_outlined),
                            label: const Text('Enregistrer les modifications'),
                          ),
                        ],
                      ),
                    ),
    );
  }
}
