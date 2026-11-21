import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:flutter/services.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';
import '../me/me_country_choices.dart';
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
  final city = TextEditingController();
  final country = TextEditingController();
  MakoloCountry? selectedCountry;
  bool countryHasUnselectedInput = false;
  bool publicProfile = false;
  bool loading = true;
  bool saving = false;
  bool authorized = false;
  String? error;
  String? loadedSpaceId;
  Map<String, dynamic>? confirmed;
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
    city.dispose();
    country.dispose();
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
      if (mounted) {
        setState(() {
          loading = false;
          authorized = false;
        });
      }
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
      final location = identity['location'] is Map
          ? identity['location'] as Map
          : const {};
      city.text = location['city']?.toString() ?? '';
      country.text = location['country']?.toString() ?? '';
      selectedCountry = countryForValue(country.text);
      countryHasUnselectedInput =
          selectedCountry == null && country.text.trim().isNotEmpty;
      setState(() {
        publicProfile = identity['public_profile'] == true;
        confirmed = {
          'name': name.text.trim(),
          'description': description.text.trim(),
          'website': website.text.trim(),
          'contact_email': email.text.trim(),
          'contact_phone': phone.text.trim(),
          'city': city.text.trim(),
          'country': country.text.trim(),
          'public_profile': publicProfile,
        };
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

  Future<void> save() async {
    final current = actor;
    final api = widget.runtime.api;
    if (!authorized ||
        saving ||
        current == null ||
        api == null ||
        current.space.id != loadedSpaceId) {
      return;
    }
    final normalizedWebsite = PassportEditorFieldRules.normalize(
      'website',
      website.text,
    );
    website.text = normalizedWebsite;
    if (form.currentState?.validate() != true) return;
    if (countryHasUnselectedInput ||
        (country.text.trim().isNotEmpty && selectedCountry == null)) {
      return;
    }
    final fields = <String, dynamic>{
      'name': name.text.trim(),
      'description': description.text.trim(),
      'website': website.text.trim(),
      'contact_email': email.text.trim(),
      'contact_phone': phone.text.trim(),
      'city': city.text.trim(),
      'country': country.text.trim(),
      'public_profile': publicProfile,
    };
    final changes = <String, dynamic>{
      for (final entry in fields.entries)
        if (confirmed == null || confirmed![entry.key] != entry.value)
          entry.key: entry.value,
    };
    if (changes.isEmpty) return;
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
          error = 'Cette modification n’est plus accessible avec vos droits actuels.';
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
      appBar: AppBar(title: const Text('Modifier notre Passeport')),
      body: current == null
          ? const Center(
              child: Text(
                'Sélectionnez l’Espace que vous êtes autorisé à modifier.',
              ),
            )
          : loading
          ? const Center(child: CircularProgressIndicator())
          : !authorized
          ? ListView(
              padding: const EdgeInsets.all(MakoloSpacing.lg),
              children: [
                Text(error ?? 'Cette modification est indisponible.'),
                MakoloActionButton(
                  label: 'Réessayer',
                  appearance: MakoloActionAppearance.quiet,
                  onPressed: load,
                  icon: Icons.refresh,
                ),
              ],
            )
          : Form(
              key: form,
              child: ListView(
                padding: const EdgeInsets.all(MakoloSpacing.lg),
                children: [
                  Text(
                    'Identité de l’Espace',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Identifiant Makolo'),
                    subtitle: Text(widget.slug),
                  ),
                  TextFormField(
                    controller: name,
                    maxLength: 180,
                    maxLengthEnforcement: MaxLengthEnforcement.none,
                    decoration: const InputDecoration(
                      labelText: 'Nom de l’Espace',
                    ),
                    validator: (v) {
                      final text = (v ?? '').trim();
                      if (text.isEmpty) return 'Nom requis.';
                      return text.runes.length > 180
                          ? '180 caractères maximum.'
                          : null;
                    },
                  ),
                  TextFormField(
                    controller: description,
                    maxLines: 4,
                    decoration: const InputDecoration(
                      labelText: 'Présentation',
                    ),
                  ),

                  const SizedBox(height: MakoloSpacing.lg),
                  Text(
                    'Localisation',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  TextFormField(
                    controller: city,
                    maxLength: 120,
                    maxLengthEnforcement: MaxLengthEnforcement.none,
                    decoration: const InputDecoration(
                      labelText: 'Ville',
                      counterText: '',
                    ),
                    validator: (value) =>
                        (value ?? '').trim().runes.length <= 120
                        ? null
                        : '120 caractères maximum.',
                  ),
                  Autocomplete<MakoloCountry>(
                    key: ValueKey(
                      'space-country-${loadedSpaceId ?? widget.slug}',
                    ),
                    initialValue: TextEditingValue(
                      text: selectedCountry?.label ?? country.text,
                    ),
                    displayStringForOption: (item) => item.label,
                    optionsBuilder: (value) {
                      final query = value.text.trim().toLowerCase();
                      if (query.isEmpty) return makoloCountries;
                      return makoloCountries.where(
                        (item) =>
                            item.label.toLowerCase().contains(query) ||
                            item.code.toLowerCase().startsWith(query),
                      );
                    },
                    onSelected: (item) {
                      setState(() {
                        selectedCountry = item;
                        country.text = item.code;
                        countryHasUnselectedInput = false;
                      });
                    },
                    fieldViewBuilder:
                        (context, editor, focusNode, onSubmitted) => Focus(
                          onFocusChange: (focused) {
                            if (focused) return;
                            final selected = countryForValue(editor.text);
                            if (selected != null) {
                              editor.value = TextEditingValue(
                                text: selected.label,
                                selection: TextSelection.collapsed(
                                  offset: selected.label.length,
                                ),
                              );
                            }
                            if (!mounted) return;
                            setState(() {
                              selectedCountry = selected;
                              country.text = selected?.code ?? '';
                              countryHasUnselectedInput =
                                  selected == null &&
                                  editor.text.trim().isNotEmpty;
                            });
                          },
                          child: TextFormField(
                            controller: editor,
                            focusNode: focusNode,
                            decoration: InputDecoration(
                              labelText: 'Pays',
                              hintText: 'Rechercher un pays',
                              prefixIcon: const Icon(Icons.public_outlined),
                              suffixIcon:
                                  selectedCountry != null &&
                                      !countryHasUnselectedInput
                                  ? const Icon(Icons.check_circle_outline)
                                  : null,
                            ),
                            onChanged: (value) {
                              final match = countryForValue(value);
                              selectedCountry = match;
                              country.text = match?.code ?? '';
                              countryHasUnselectedInput =
                                  match == null && value.trim().isNotEmpty;
                            },
                            validator: (value) {
                              if ((value ?? '').trim().isEmpty) return null;
                              return countryForValue(value!) == null
                                  ? 'Choisissez un pays dans la liste.'
                                  : null;
                            },
                          ),
                        ),
                  ),
                  const SizedBox(height: MakoloSpacing.lg),
                  Text(
                    'Contact',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  TextFormField(
                    controller: email,
                    keyboardType: TextInputType.emailAddress,
                    textCapitalization: TextCapitalization.none,
                    maxLength: 254,
                    maxLengthEnforcement: MaxLengthEnforcement.none,
                    decoration: const InputDecoration(
                      labelText: 'Adresse e-mail',
                      counterText: '',
                    ),
                    validator: (value) {
                      final text = (value ?? '').trim();
                      if (text.isEmpty) return null;
                      if (text.runes.length > 254) {
                        return '254 caractères maximum.';
                      }
                      return RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
                              .hasMatch(text)
                          ? null
                          : 'E-mail invalide.';
                    },
                  ),
                  TextFormField(
                    controller: phone,
                    keyboardType: TextInputType.phone,
                    maxLength: 40,
                    maxLengthEnforcement: MaxLengthEnforcement.none,
                    decoration: const InputDecoration(
                      labelText: 'Téléphone',
                      counterText: '',
                    ),
                    validator: (value) {
                      final text = (value ?? '').trim();
                      if (text.isEmpty) return null;
                      if (text.runes.length > 40) {
                        return '40 caractères maximum.';
                      }
                      final digits = RegExp(r'[0-9]').allMatches(text).length;
                      return RegExp(
                                r'^(?:\+?[0-9][0-9().\s-]*|\(\+[0-9]{1,4}\)[0-9().\s-]*)$',
                              ).hasMatch(text) &&
                              digits >= 7 &&
                              digits <= 15
                          ? null
                          : 'Téléphone invalide.';
                    },
                  ),

                  const SizedBox(height: MakoloSpacing.lg),
                  Text('Liens', style: Theme.of(context).textTheme.titleMedium),
                  Focus(
                    onFocusChange: (focused) {
                      if (!focused && !saving) {
                        final normalized = PassportEditorFieldRules.normalize(
                          'website',
                          website.text,
                        );
                        if (website.text != normalized) {
                          setState(() => website.text = normalized);
                        }
                      }
                    },
                    child: TextFormField(
                      controller: website,
                      keyboardType: TextInputType.url,
                      textCapitalization: TextCapitalization.none,
                      autocorrect: false,
                      maxLength: 200,
                      maxLengthEnforcement: MaxLengthEnforcement.none,
                      decoration: const InputDecoration(
                        labelText: 'Site web',
                        counterText: '',
                      ),
                      validator: (value) => PassportEditorFieldRules.error(
                        'website',
                        value ?? '',
                      ),
                    ),
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
                  MakoloActionButton(
                    label: saving
                        ? 'Enregistrement…'
                        : 'Enregistrer les modifications',
                    appearance: MakoloActionAppearance.primary,
                    busy: saving,
                    onPressed: saving ? null : save,
                    icon: Icons.save_outlined,
                  ),
                ],
              ),
            ),
    );
  }
}
