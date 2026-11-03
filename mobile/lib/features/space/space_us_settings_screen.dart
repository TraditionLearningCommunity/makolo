import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';
import '../me/passport_editor_field_rules.dart';

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
  Map<String, dynamic>? confirmed;
  final Map<String, String> localErrors = {};
  int loadVersion = 0;

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(onActorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => unawaited(load()));
  }

  void onActorChanged() {
    if (!mounted) return;
    loadVersion++;
    setState(() {
      authorized = false;
      loadedSpaceId = null;
    });
    if (actor != null) unawaited(load());
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

  String get usPath =>
      'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/us/';

  Future<void> load() async {
    final version = ++loadVersion;
    final current = actor;
    final api = widget.runtime.api;
    if (current == null || api == null) {
      if (mounted)
        setState(() {
          loading = false;
          authorized = false;
        });
      return;
    }
    final expectedId = current.space.id;
    setState(() {
      loading = true;
      error = null;
      authorized = false;
    });
    try {
      final response = await api.get(usPath);
      final payload = response.jsonObject();
      final identity = payload['identity'];
      final caps = payload['capabilities'];
      if (identity is! Map ||
          caps is! Map ||
          identity['id']?.toString() != expectedId ||
          caps['update_space'] != true) {
        throw const FormatException('Settings not available for this actor');
      }
      if (!mounted || version != loadVersion || actor?.space.id != expectedId) {
        return;
      }
      name.text = identity['name']?.toString() ?? '';
      description.text = identity['description']?.toString() ?? '';
      website.text = identity['website']?.toString() ?? '';
      email.text = identity['contact_email']?.toString() ?? '';
      phone.text = identity['contact_phone']?.toString() ?? '';
      setState(() {
        publicProfile = identity['public_profile'] == true;
        confirmed = values();
        localErrors.clear();
        authorized = true;
        loading = false;
        loadedSpaceId = expectedId;
      });
    } on Object {
      if (!mounted || version != loadVersion || actor?.space.id != expectedId) {
        return;
      }
      setState(() {
        loading = false;
        authorized = false;
        error =
            'Impossible de vérifier les droits et les informations '
            'actuelles. Reconnectez-vous puis réessayez.';
      });
    }
  }

  Map<String, dynamic> values() => {
    'name': name.text.trim(),
    'description': description.text.trim(),
    'website': website.text.trim(),
    'contact_email': email.text.trim(),
    'contact_phone': phone.text.trim(),
    'public_profile': publicProfile,
  };

  String? check(String key, String raw) {
    final text = raw.trim();
    if (key == 'name') {
      if (text.isEmpty) return 'Nom requis.';
      if (text.runes.length > 180) return '180 caractères maximum.';
    }
    if (key == 'website') {
      return PassportEditorFieldRules.error('website', text);
    }
    if (key == 'contact_email' && text.isNotEmpty) {
      if (text.length > 254 ||
          !RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+
    final current = actor;
    final api = widget.runtime.api;
    if (!authorized ||
        saving ||
        current == null ||
        api == null ||
        current.space.id != loadedSpaceId ||
        form.currentState?.validate() != true) {
      return;
    }
    final expectedId = current.space.id;
    setState(() {
      saving = true;
      error = null;
    });
    try {
      // No local mutation: the server checks SPACE_MANAGE at PATCH time.
      await api.patch(
        'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/',
        body: changes,
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
      if (failure.statusCode == 401 ||
          failure.statusCode == 403 ||
          failure.statusCode == 404) {
        setState(() {
          authorized = false;
          error =
              'Votre autorité a changé. Cet espace ne peut plus être modifié.';
        });
      } else {
        setState(() {
          error = failure.message;
        });
      }
    } on Object {
      if (!mounted || actor?.space.id != expectedId) return;
      setState(() {
        error =
            'Impossible de confirmer l’enregistrement. '
            'Actualisez les informations avant de réessayer.';
      });
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = actor;
    return Scaffold(
      appBar: AppBar(title: const Text('Identité de l’Espace')),
      body: current == null
          ? const Center(
              child: Text('Sélectionnez l’Espace que vous êtes autorisé à modifier.'),
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
                  Text(
                    'Informations collectives',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                  const SizedBox(height: MakoloSpacing.md),
                  field('name', name,
                    label: 'Nom de l’Espace', maxLength: 180),
                  field('description', description,
                    label: 'Présentation', lines: 4,
                    keyboard: TextInputType.multiline),
                  field('website', website,
                    label: 'Site web', maxLength: 200,
                    keyboard: TextInputType.url),
                  field('contact_email', email,
                    label: 'Adresse e-mail', maxLength: 254,
                    keyboard: TextInputType.emailAddress),
                  field('contact_phone', phone,
                    label: 'Téléphone', maxLength: 50,
                    keyboard: TextInputType.phone),
                  SwitchListTile.adaptive(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Profil public'),
                    value: publicProfile,
                    onChanged: saving
                        ? null
                        : (value) => setState(() => publicProfile = value),
                  ),
                  if (error != null) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ],
                  const SizedBox(height: MakoloSpacing.md),
                  FilledButton.icon(
                    onPressed: saving ? null : save,
                    icon: saving
                        ? const SizedBox(
                            height: 16,
                            width: 16,
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
).hasMatch(text)) {
        return 'E-mail invalide.';
      }
    }
    if (key == 'contact_phone' && text.isNotEmpty) {
      if (text.runes.length > 50 ||
          !RegExp(r'^\+?[0-9().\s-]+
    final current = actor;
    final api = widget.runtime.api;
    if (!authorized ||
        saving ||
        current == null ||
        api == null ||
        current.space.id != loadedSpaceId ||
        form.currentState?.validate() != true) {
      return;
    }
    final expectedId = current.space.id;
    setState(() {
      saving = true;
      error = null;
    });
    try {
      // No local mutation: the server checks SPACE_MANAGE at PATCH time.
      await api.patch(
        'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/',
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
      if (failure.statusCode == 401 ||
          failure.statusCode == 403 ||
          failure.statusCode == 404) {
        setState(() {
          authorized = false;
          error =
              'Votre autorité a changé. Cet espace ne peut plus être modifié.';
        });
      } else {
        setState(() {
          error = failure.message;
        });
      }
    } on Object {
      if (!mounted || actor?.space.id != expectedId) return;
      setState(() {
        error =
            'Impossible de confirmer l’enregistrement. '
            'Actualisez les informations avant de réessayer.';
      });
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = actor;
    return Scaffold(
      appBar: AppBar(title: const Text('Identité de l’Espace')),
      body: current == null
          ? const Center(
              child: Text('Sélectionnez l’Espace que vous êtes autorisé à modifier.'),
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
                  Text(
                    'Informations collectives',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                  const SizedBox(height: MakoloSpacing.md),
                  TextFormField(
                    controller: name,
                    maxLength: 180,
                    decoration: const InputDecoration(
                      labelText: 'Nom de l’Espace',
                    ),
                    validator: (v) => (v?.trim().isEmpty ?? true)
                        ? 'Le nom est nécessaire.'
                        : null,
                  ),
                  TextFormField(
                    controller: description,
                    maxLines: 4,
                    decoration: const InputDecoration(
                      labelText: 'Présentation',
                    ),
                  ),
                  TextFormField(
                    controller: website,
                    keyboardType: TextInputType.url,
                    decoration: const InputDecoration(labelText: 'Site web'),
                  ),
                  TextFormField(
                    controller: email,
                    keyboardType: TextInputType.emailAddress,
                    decoration: const InputDecoration(
                      labelText: 'Contact général',
                    ),
                  ),
                  TextFormField(
                    controller: phone,
                    keyboardType: TextInputType.phone,
                    decoration: const InputDecoration(
                      labelText: 'Téléphone général',
                    ),
                  ),
                  SwitchListTile.adaptive(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Profil public'),
                    value: publicProfile,
                    onChanged: saving
                        ? null
                        : (value) => setState(() => publicProfile = value),
                  ),
                  if (error != null) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ],
                  const SizedBox(height: MakoloSpacing.md),
                  FilledButton.icon(
                    onPressed: saving ? null : save,
                    icon: saving
                        ? const SizedBox(
                            height: 16,
                            width: 16,
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
).hasMatch(text)) {
        return 'Téléphone invalide.';
      }
      final digits = RegExp(r'[0-9]').allMatches(text).length;
      if (digits < 7 || digits > 15) return '7 à 15 chiffres.';
    }
    return null;
  }

  void validateField(String key, TextEditingController controller) {
    if (!mounted || saving) return;
    final normalized = key == 'website'
        ? PassportEditorFieldRules.normalize('website', controller.text)
        : controller.text.trim();
    if (normalized != controller.text) {
      controller.value = TextEditingValue(
        text: normalized,
        selection: TextSelection.collapsed(offset: normalized.length),
      );
    }
    final issue = check(key, normalized);
    setState(() {
      if (issue == null) {
        localErrors.remove(key);
      } else {
        localErrors[key] = issue;
      }
    });
  }

  Widget field(String key, TextEditingController controller, {
    required String label,
    int? maxLength,
    int lines = 1,
    TextInputType? keyboard,
  }) => Focus(
    onFocusChange: (focused) {
      if (!focused && authorized) validateField(key, controller);
    },
    child: TextFormField(
      controller: controller,
      maxLength: maxLength,
      maxLines: lines,
      keyboardType: keyboard,
      textCapitalization: key == 'website' || key == 'contact_email' ||
              key == 'contact_phone'
          ? TextCapitalization.none : TextCapitalization.sentences,
      autocorrect: key != 'website' && key != 'contact_email',
      decoration: InputDecoration(
        labelText: label, errorText: localErrors[key],
        counterText: '',
      ),
      onChanged: (text) {
        if (!localErrors.containsKey(key)) return;
        final issue = check(key, text);
        setState(() {
          if (issue == null) {
            localErrors.remove(key);
          } else {
            localErrors[key] = issue;
          }
        });
      },
    ),
  );

  Future<void> save() async {
    final current = actor;
    final api = widget.runtime.api;
    if (!authorized || saving || current == null ||
        api == null || current.space.id != loadedSpaceId) return;
    final editors = <String, TextEditingController>{
      'name': name, 'description': description, 'website': website,
      'contact_email': email, 'contact_phone': phone,
    };
    final errors = <String, String>{};
    for (final entry in editors.entries) {
      if (confirmed?[entry.key] == entry.value.text) continue;
      final text = entry.key == 'website'
          ? PassportEditorFieldRules.normalize('website', entry.value.text)
          : entry.value.text.trim();
      if (text != entry.value.text) {
        entry.value.value = TextEditingValue(
          text: text, selection: TextSelection.collapsed(offset: text.length),
        );
      }
      final issue = check(entry.key, text);
      if (issue != null) errors[entry.key] = issue;
    }
    if (errors.isNotEmpty) {
      setState(() { localErrors.addAll(errors); error = null; });
      return;
    }
    final changes = <String, dynamic>{
      for (final entry in values().entries)
        if (confirmed == null || confirmed![entry.key] != entry.value)
          entry.key: entry.value,
    };
    if (changes.isEmpty) return;
    final expectedId = current.space.id;
    setState(() { saving = true; error = null; });
    try {
      // No local mutation: the server checks SPACE_MANAGE at PATCH time.
      await api.patch(
        'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/',
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
      if (failure.statusCode == 401 ||
          failure.statusCode == 403 ||
          failure.statusCode == 404) {
        setState(() {
          authorized = false;
          error =
              'Votre autorité a changé. Cet espace ne peut plus être modifié.';
        });
      } else {
        setState(() {
          error = failure.message;
        });
      }
    } on Object {
      if (!mounted || actor?.space.id != expectedId) return;
      setState(() {
        error =
            'Impossible de confirmer l’enregistrement. '
            'Actualisez les informations avant de réessayer.';
      });
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = actor;
    return Scaffold(
      appBar: AppBar(title: const Text('Identité de l’Espace')),
      body: current == null
          ? const Center(
              child: Text('Sélectionnez l’Espace que vous êtes autorisé à modifier.'),
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
                  Text(
                    'Informations collectives',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                  const SizedBox(height: MakoloSpacing.md),
                  TextFormField(
                    controller: name,
                    maxLength: 180,
                    decoration: const InputDecoration(
                      labelText: 'Nom de l’Espace',
                    ),
                    validator: (v) => (v?.trim().isEmpty ?? true)
                        ? 'Le nom est nécessaire.'
                        : null,
                  ),
                  TextFormField(
                    controller: description,
                    maxLines: 4,
                    decoration: const InputDecoration(
                      labelText: 'Présentation',
                    ),
                  ),
                  TextFormField(
                    controller: website,
                    keyboardType: TextInputType.url,
                    decoration: const InputDecoration(labelText: 'Site web'),
                  ),
                  TextFormField(
                    controller: email,
                    keyboardType: TextInputType.emailAddress,
                    decoration: const InputDecoration(
                      labelText: 'Contact général',
                    ),
                  ),
                  TextFormField(
                    controller: phone,
                    keyboardType: TextInputType.phone,
                    decoration: const InputDecoration(
                      labelText: 'Téléphone général',
                    ),
                  ),
                  SwitchListTile.adaptive(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Profil public'),
                    value: publicProfile,
                    onChanged: saving
                        ? null
                        : (value) => setState(() => publicProfile = value),
                  ),
                  if (error != null) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ],
                  const SizedBox(height: MakoloSpacing.md),
                  FilledButton.icon(
                    onPressed: saving ? null : save,
                    icon: saving
                        ? const SizedBox(
                            height: 16,
                            width: 16,
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
