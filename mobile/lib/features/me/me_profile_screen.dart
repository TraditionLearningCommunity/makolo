import 'dart:io';

import '../../navigation/profile_portrait_store.dart';

import 'package:flutter/material.dart';

import '../../network/makolo_api_client.dart';
import '../../platform/camera/system_media_picker.dart';
import '../../repositories/personal_repository.dart';
import '../../repositories/draft_repository.dart';
import '../../sync/projection_contract.dart';
import 'me_local_preview.dart';
import 'me_country_choices.dart';

/// Passport editing mode backed by the existing Accounts owner API.
class MeProfileScreen extends StatefulWidget {
  const MeProfileScreen({super.key, required this.api, required this.personal,
    this.drafts, this.openAvatarPicker = false});
  final MakoloApiClient api;
  final PersonalRepository personal;
  final DraftRepository? drafts;
  final bool openAvatarPicker;

  @override
  State<MeProfileScreen> createState() => _MeProfileScreenState();
}

class _MeProfileScreenState extends State<MeProfileScreen> {
  static const _accountEditorProjection = 'personal.me.account_editor';
  final _firstName = TextEditingController();
  final _lastName = TextEditingController();
  final _profession = TextEditingController();
  final _city = TextEditingController();
  final _country = TextEditingController();
  final _bio = TextEditingController();
  final _phone = TextEditingController();
  final _website = TextEditingController();
  final _linkedin = TextEditingController();
  final _facebook = TextEditingController();
  final _instagram = TextEditingController();
  final _tiktok = TextEditingController();
  final _x = TextEditingController();
  final _youtube = TextEditingController();
  final _company = TextEditingController();
  final _organization = TextEditingController();
  final _language = TextEditingController();
  final _address = TextEditingController();
  bool _publicProfile = false;
  bool _searchable = false;
  MakoloCountry? _selectedCountry;
  bool _countryHasUnselectedInput = false;

  bool _avatarPickerScheduled = false;
  bool _loading = true;
  bool _loaded = false;
  bool _saving = false;
  String? _error;
  String? _confirmation;
  Map<String, dynamic>? _cachedIdentity;
  bool _edited = false;
  Future<void> _draftWrites = Future<void>.value();

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  /// Whitelist the Accounts editor fields. Do not persist the full auth
  /// response, credentials, tokens or unrelated Profile information.
  static Map<String, dynamic> _editorProjection(Map<String, dynamic> user) {
    final profile = user['profile'];
    final fields = profile is Map ? profile : const <String, dynamic>{};
    return {
      for (final key in const [
        'first_name', 'last_name', 'bio', 'phone', 'website',
        'linkedin_url', 'facebook_url', 'instagram_url', 'tiktok_url',
        'x_url', 'youtube_url', 'language',
      ])
        key: user[key]?.toString() ?? '',
      for (final key in const [
        'profession', 'city', 'country', 'company_name',
        'organization_name', 'address',
      ])
        key: fields[key]?.toString() ?? '',
      'public_profile': fields['public_profile'] == true,
      'searchable': fields['searchable'] == true,
    };
  }

  void _applyEditor(Map<String, dynamic> editor) {
    String value(String key) => editor[key]?.toString() ?? '';
    _firstName.text = value('first_name');
    _lastName.text = value('last_name');
    _bio.text = value('bio');
    _profession.text = value('profession');
    _city.text = value('city');
    _country.text = value('country');
    _selectedCountry = countryForValue(_country.text);
    _countryHasUnselectedInput = false;
    _phone.text = value('phone');
    _website.text = value('website');
    _linkedin.text = value('linkedin_url');
    _facebook.text = value('facebook_url');
    _instagram.text = value('instagram_url');
    _tiktok.text = value('tiktok_url');
    _x.text = value('x_url');
    _youtube.text = value('youtube_url');
    _company.text = value('company_name');
    _organization.text = value('organization_name');
    _language.text = value('language');
    _address.text = value('address');
    _publicProfile = editor['public_profile'] == true;
    _searchable = editor['searchable'] == true;
    _loading = false;
    _loaded = true;
  }

  Future<void> _persistEditor(Map<String, dynamic> editor) async {
    await widget.personal.store.putProjection(
      kind: _accountEditorProjection,
      schemaVersion: 1,
      payload: editor,
    );
  }

  static const _draftOwner = 'Accounts';
  static const _draftKind = 'profile_editor';

  Map<String, dynamic> _currentEditor() => {
    'first_name': _firstName.text.trim(),
    'last_name': _lastName.text.trim(),
    'bio': _bio.text.trim(),
    'profession': _profession.text.trim(),
    'city': _city.text.trim(),
    'country': _selectedCountry?.code ?? '',
    'phone': _phone.text.trim(),
    'website': _website.text.trim(),
    'linkedin_url': _linkedin.text.trim(),
    'facebook_url': _facebook.text.trim(),
    'instagram_url': _instagram.text.trim(),
    'tiktok_url': _tiktok.text.trim(),
    'x_url': _x.text.trim(),
    'youtube_url': _youtube.text.trim(),
    'company_name': _company.text.trim(),
    'organization_name': _organization.text.trim(),
    'language': 'fr',
    'address': _address.text.trim(),
    'public_profile': _publicProfile,
    'searchable': _searchable,
  };

  void _rememberEdits() {
    _edited = true;
    final drafts = widget.drafts;
    if (drafts == null || !_loaded) return;
    final payload = _currentEditor();
    final profileId = widget.personal.store.profileId;
    _draftWrites = _draftWrites.catchError((Object _) {}).then((_) =>
        drafts.saveLocal(
          draftId: 'accounts-profile-editor-$profileId',
          owner: _draftOwner,
          resourceKind: _draftKind,
          resourceId: profileId,
          payload: payload,
        ));
  }

  Future<void> _bootstrap() async {
    try {
      final snapshot = await widget.personal.store.readProjection('personal.me');
      final local = MeLocalPreview.forProfile(
        snapshot,
        widget.personal.store.profileId,
      );
      final editor = await widget.personal.store.readProjection(
        _accountEditorProjection,
      );
      final draft = await widget.drafts?.read(
        owner: _draftOwner,
        resourceKind: _draftKind,
        resourceId: widget.personal.store.profileId,
      );
      if (mounted) {
        setState(() {
          _cachedIdentity = local?.identity;
          if (editor != null) {
            _applyEditor(editor.payload);
          }
          if (draft != null && editor != null) {
            // Device-owned draft is not a confirmed Accounts fact.
            _applyEditor(draft.payload);
            _edited = true;
          } else if (editor == null && local?.identity != null) {
            _loading = false;
          }
        });
      }
    } on Object {
      // Missing local facts do not block the Accounts owner acquisition.
    }
    if (mounted) await _read();
  }

  Future<void> _read() async {
    try {
      final response = await widget.api.get('api/v1/accounts/auth/me/');
      final editor = _editorProjection(response.jsonObject());
      try {
        await _persistEditor(editor);
      } on Object {
        // A valid Accounts reply can still render if local storage is full.
      }
      if (!mounted) return;
      setState(() {
        // Never overwrite text entered while the background check was
        // pending. Those edits are not yet confirmed by the owner.
        if (!_edited) _applyEditor(editor);
        _loading = false;
        _error = null;
      });
      if (widget.openAvatarPicker && !_avatarPickerScheduled) {
        _avatarPickerScheduled = true;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _changeAvatar();
        });
      }
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        // Keep a fully received Accounts editor on-screen, rather than
        // replacing it with only the Profile's name and biography.
        if (!_loaded) {
          _error = 'Modification indisponible sans confirmation du serveur.';
        }
      });
    }
  }

  Future<void> _changeAvatar() async {
    if (_saving || !_loaded) return;
    final source = await showModalBottomSheet<bool>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            leading: const Icon(Icons.photo_library_outlined),
            title: const Text('Choisir une photo'),
            onTap: () => Navigator.pop(context, false),
          ),
          ListTile(
            leading: const Icon(Icons.photo_camera_outlined),
            title: const Text('Prendre une photo'),
            onTap: () => Navigator.pop(context, true),
          ),
        ],
      )),
    );
    if (source == null || !mounted) return;
    try {
      final image = await ImagePickerSystemMediaPicker()
          .pickImage(capture: source);
      if (image == null || !mounted) return;
      final approved = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Modifier la photo'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ClipOval(child: Image.file(
                File(image.path),
                width: 152, height: 152, fit: BoxFit.cover,
                errorBuilder: (_, _, _) => const Icon(Icons.person, size: 90),
              )),
              const SizedBox(height: 14),
              const Text('Utiliser cette photo sur mon passeport ?'),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Annuler'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Confirmer'),
            ),
          ],
        ),
      );
      if (approved != true || !mounted) return;
      setState(() { _saving = true; _error = null; _confirmation = null; });
      await widget.api.upload(
        'api/v1/accounts/auth/profile/update/',
        method: 'PATCH',
        files: [MakoloUploadFile(
          fieldName: 'avatar', path: image.path, filename: image.name,
        )],
      );
      // Keep the confirmed portrait in the durable private file area, not OS
      // image cache. Owner projection refresh still reconciles the server fact.
      try {
        await ProfilePortraitStore(widget.personal.store.profileId)
            .savePickedFile(image.path);
      } on Object {
        // A later authenticated read can rehydrate the authorized portrait.
      }
      final fresh = await _refreshPersonal();
      if (!mounted) return;
      setState(() {
        _saving = false;
        _confirmation = fresh
            ? 'Photo mise à jour.'
            : 'Photo enregistrée. Actualisation en attente.';
      });
    } on Object {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = 'Impossible de modifier la photo.';
        });
      }
    }
  }

  Future<bool> _refreshPersonal() async {
    try {
      final response = await widget.api.get('api/v1/me/');
      final envelope = ProjectionEnvelope.parse(
        response.jsonObject(), expectedProjection: 'personal.me',
      );
      final actor = envelope.data['actor'];
      if (actor is! Map ||
          actor['id']?.toString() != widget.personal.store.profileId) {
        return false;
      }
      await widget.personal.store.putProjection(
        kind: 'personal.me',
        schemaVersion: envelope.schemaVersion,
        payload: envelope.data,
        sourceGeneratedAt: envelope.generatedAt,
        receivedAt: DateTime.now().toUtc(),
      );
      return true;
    } on Object {
      return false;
    }
  }

  Future<void> _save() async {
    if (_saving || _loading) return;
    if (_countryHasUnselectedInput ||
        (_country.text.trim().isNotEmpty && _selectedCountry == null)) {
      setState(() => _error = 'Choisissez un pays dans les suggestions.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
      _confirmation = null;
    });
    try {
      await widget.api.patch(
        'api/v1/accounts/auth/profile/update/',
        body: {
          'first_name': _firstName.text.trim(),
          'last_name': _lastName.text.trim(),
          'profession': _profession.text.trim(),
          'city': _city.text.trim(),
          'country': _selectedCountry?.code ?? '',
          'bio': _bio.text.trim(),
          'phone': _phone.text.trim(),
          'website': _website.text.trim(),
          'linkedin_url': _linkedin.text.trim(),
          'facebook_url': _facebook.text.trim(),
          'instagram_url': _instagram.text.trim(),
          'tiktok_url': _tiktok.text.trim(),
          'x_url': _x.text.trim(),
          'youtube_url': _youtube.text.trim(),
          'company_name': _company.text.trim(),
          'organization_name': _organization.text.trim(),
          'language': 'fr',
          'address': _address.text.trim(),
          'public_profile': _publicProfile,
          'searchable': _searchable,
        },
      );
    } on Object {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = 'Impossible d’enregistrer ces modifications.';
      });
      return;
    }

    // Accounts confirmed these fields. Clear the device-owned draft only
    // after the last local write has completed.
    try {
      await _persistEditor(_currentEditor());
    } on Object {
      // The remote success is not undone by a local storage failure.
    }
    try {
      await _draftWrites;
      await widget.drafts?.delete(
        owner: _draftOwner,
        resourceKind: _draftKind,
        resourceId: widget.personal.store.profileId,
      );
    } on Object {
      // An already-confirmed owner mutation remains confirmed.
    }
    _edited = false;
    final refreshed = await _refreshPersonal();
    if (!mounted) return;
    setState(() {
      _saving = false;
      _confirmation = refreshed
          ? 'Modifications enregistrées.'
          : 'Enregistré. Actualisation en attente.';
    });
  }

  @override
  void dispose() {
    for (final controller in [
      _firstName,
      _lastName,
      _profession,
      _city,
      _country,
      _bio,
      _phone, _website, _linkedin, _facebook, _instagram,
      _tiktok, _x, _youtube, _company, _organization,
      _language, _address,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Modifier mon passeport')),
      body: _loading && _cachedIdentity == null
          ? const Center(child: CircularProgressIndicator.adaptive())
          : !_loaded
          ? _localSummary(context)
          : ListView(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 44),
              children: [
                if (_error != null) ...[
                  Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (!_saving && _confirmation == null)
                    TextButton(
                      onPressed: _read,
                      child: const Text('Réessayer'),
                    ),
                ],
                if (_confirmation != null) ...[
                  Text(
                    _confirmation!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.primary,
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
                _sectionTitle('Identité'),
                _field('Prénom', _firstName),
                _field('Nom', _lastName),
                _field('Profession', _profession),
                _field('À propos', _bio, lines: 3),
                OutlinedButton.icon(
                  onPressed: _saving ? null : _changeAvatar,
                  icon: const Icon(Icons.photo_camera_outlined),
                  label: const Text('Modifier la photo'),
                ),
                _sectionTitle('Localisation'),
                _countryAutocomplete(),
                _field('Ville', _city),
                _field('Adresse', _address),
                _sectionTitle('Contact et activité'),
                _field('Téléphone', _phone),
                _field('Site web', _website),
                _field('Entreprise', _company),
                _field('Organisation', _organization),
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: DropdownButtonFormField<String>(
                    initialValue: 'fr',
                    decoration: const InputDecoration(
                      labelText: 'Langue',
                      border: OutlineInputBorder(),
                    ),
                    items: const [
                      DropdownMenuItem(value: 'fr', child: Text('Français')),
                    ],
                    onChanged: _saving ? null : (value) {
                      _language.text = value ?? 'fr';
                      _rememberEdits();
                    },
                  ),
                ),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('Réseaux sociaux'),
                  subtitle: const Text('Liens facultatifs'),
                  children: [
                    _field('LinkedIn', _linkedin),
                    _field('Facebook', _facebook),
                    _field('Instagram', _instagram),
                    _field('TikTok', _tiktok),
                    _field('X', _x),
                    _field('YouTube', _youtube),
                  ],
                ),
                _sectionTitle('Visibilité'),
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Passeport public'),
                  subtitle: const Text('Autoriser la présentation publique'),
                  value: _publicProfile,
                  onChanged: _saving ? null : (value) =>
                      setState(() {
                        _publicProfile = value;
                        _rememberEdits();
                      }),
                ),
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Visible dans la recherche'),
                  value: _searchable,
                  onChanged: _saving ? null : (value) =>
                      setState(() {
                        _searchable = value;
                        _rememberEdits();
                      }),
                ),
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: _saving ? null : _save,
                  child: Text(_saving ? 'Enregistrement…' : 'Enregistrer'),
                ),
              ],
            ),
    );
  }

  Widget _localSummary(BuildContext context) {
    final identity = _cachedIdentity;
    final name = identity?['display_name']?.toString();
    final bio = identity?['bio']?.toString();
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 40),
      children: [
        Text(
          identity == null
              ? 'Les informations du profil ne sont pas encore '
                  'disponibles sur cet appareil.'
              : 'Dernières informations du profil connues sur cet appareil. '
                  'La modification nécessite une connexion.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        if (name != null && name.trim().isNotEmpty) ...[
          const SizedBox(height: 20),
          Text(name, style: Theme.of(context).textTheme.titleLarge),
        ],
        if (bio != null && bio.trim().isNotEmpty) ...[
          const SizedBox(height: 12),
          Text(bio),
        ],
        const SizedBox(height: 20),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: _read,
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Réessayer'),
          ),
        ),
      ],
    );
  }

  Widget _sectionTitle(String title) => Padding(
    padding: const EdgeInsets.only(top: 24, bottom: 16),
    child: Text(
      title,
      style: Theme.of(context).textTheme.titleMedium?.copyWith(
        fontWeight: FontWeight.w700,
      ),
    ),
  );

  Widget _countryAutocomplete() => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: Autocomplete<MakoloCountry>(
      initialValue: TextEditingValue(
        text: _selectedCountry?.label ?? _country.text,
      ),
      displayStringForOption: (country) => country.label,
      optionsBuilder: (value) {
        final query = value.text.trim().toLowerCase();
        if (query.isEmpty) {
          return makoloCountries.take(30);
        }
        return makoloCountries.where((country) =>
          country.label.toLowerCase().contains(query) ||
          country.code.toLowerCase().startsWith(query));
      },
      onSelected: (country) {
        setState(() {
          _selectedCountry = country;
          _country.text = country.code;
          _countryHasUnselectedInput = false;
        });
        _rememberEdits();
      },
      fieldViewBuilder: (context, controller, focusNode, onFieldSubmitted) =>
          TextFormField(
            controller: controller,
            focusNode: focusNode,
            textCapitalization: TextCapitalization.sentences,
            decoration: const InputDecoration(
              labelText: 'Pays',
              hintText: 'Rechercher un pays',
              prefixIcon: Icon(Icons.public_outlined),
              border: OutlineInputBorder(),
              isDense: true,
              contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 15),
            ),
            onChanged: (value) {
              if (value != _selectedCountry?.label) {
                _selectedCountry = null;
                _country.clear();
                _countryHasUnselectedInput = value.trim().isNotEmpty;
                _rememberEdits();
              }
            },
            onFieldSubmitted: (value) => onFieldSubmitted(),
          ),
    ),
  );

  Widget _field(
    String label,
    TextEditingController controller, {
    int lines = 1,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: TextField(
      controller: controller,
      onChanged: (_) => _rememberEdits(),
      maxLines: lines,
      textCapitalization: TextCapitalization.sentences,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 15),
      ),
    ),
  );
}
