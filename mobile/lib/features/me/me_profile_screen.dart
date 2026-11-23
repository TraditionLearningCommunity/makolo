import 'dart:io';

import '../../navigation/profile_portrait_store.dart';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:flutter/services.dart';

import '../../network/makolo_api_client.dart';
import '../../network/api_error.dart';
import '../../platform/camera/system_media_picker.dart';
import '../../repositories/personal_repository.dart';
import '../../repositories/draft_repository.dart';
import '../../sync/projection_contract.dart';
import '../../sync/sync_engine.dart';
import 'me_local_preview.dart';
import 'me_country_choices.dart';
import 'passport_editor_field_rules.dart';

/// Passport editing mode backed by the existing Accounts owner API.
class MeProfileScreen extends StatefulWidget {
  const MeProfileScreen({
    super.key,
    required this.api,
    required this.personal,
    this.sync,
    this.drafts,
    this.openAvatarPicker = false,
    this.focusVisibility = false,
  });
  final MakoloApiClient api;
  final PersonalRepository personal;
  final SyncEngine? sync;
  final DraftRepository? drafts;
  final bool openAvatarPicker;
  final bool focusVisibility;

  @override
  State<MeProfileScreen> createState() => _MeProfileScreenState();
}

class _MeProfileScreenState extends State<MeProfileScreen> {
  static const _accountEditorProjection = 'personal.me.account_editor';
  final _firstName = TextEditingController();
  final _lastName = TextEditingController();
  final _birthDate = TextEditingController();
  String _gender = 'unspecified';
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
  final _address = TextEditingController();
  bool _publicProfile = true;
  bool _searchable = true;
  MakoloCountry? _selectedCountry;
  bool _countryHasUnselectedInput = false;

  bool _avatarPickerScheduled = false;
  bool _visibilityJumpScheduled = false;
  final ScrollController _scrollController = ScrollController();
  final GlobalKey _visibilityAnchor = GlobalKey();
  bool _loading = true;
  bool _loaded = false;
  bool _saving = false;
  String? _error;
  bool _saveFailedRemotely = false;
  Map<String, String> _fieldErrors = const {};
  final Set<String> _checkedFields = {};
  String? _confirmation;
  Map<String, dynamic>? _cachedIdentity;
  Map<String, dynamic>? _confirmedEditor;
  // Owner account details are read-only here; never stored in the draft/PATCH.
  String? _accountEmail;
  String? _accountIdentifier;
  bool _edited = false;
  Future<void> _draftWrites = Future<void>.value();
  Map<String, dynamic>? _nextDraftSnapshot;
  bool _draftWorkerActive = false;
  int _editRevision = 0;

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
        'first_name',
        'last_name',
        'bio',
        'phone',
        'website',
        'linkedin_url',
        'facebook_url',
        'instagram_url',
        'tiktok_url',
        'x_url',
        'youtube_url',
      ])
        key: user[key]?.toString() ?? '',
      for (final key in const [
        'profession',
        'city',
        'country',
        'company_name',
        'organization_name',
        'address',
      ])
        key: fields[key]?.toString() ?? '',
      'birth_date': user['birth_date']?.toString().trim().isNotEmpty == true
          ? user['birth_date'].toString()
          : null,
      'gender':
          const {
            'male',
            'female',
            'unspecified',
          }.contains(user['gender']?.toString())
          ? user['gender'].toString()
          : 'unspecified',
      'public_profile': fields['public_profile'] != false,
      'searchable': fields['searchable'] != false,
    };
  }

  void _applyEditor(Map<String, dynamic> editor) {
    String value(String key) => editor[key]?.toString() ?? '';
    _firstName.text = value('first_name');
    _lastName.text = value('last_name');
    _birthDate.text = value('birth_date');
    _gender = const {'male', 'female', 'unspecified'}.contains(value('gender'))
        ? value('gender')
        : 'unspecified';
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
    _address.text = value('address');
    _publicProfile = editor['public_profile'] != false;
    _searchable = editor['searchable'] != false;
    _checkedFields.clear();
    _fieldErrors = const {};
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
    'birth_date': _birthDate.text.trim().isEmpty
        ? null
        : _birthDate.text.trim(),
    'gender': _gender,
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
    'address': _address.text.trim(),
    'public_profile': _publicProfile,
    'searchable': _searchable,
  };

  static const Map<String, String> _fieldKeys = {
    'Prénom': 'first_name',
    'Nom': 'last_name',
    'À propos': 'bio',
    'Profession': 'profession',
    'Ville': 'city',
    'Adresse': 'address',
    'Téléphone': 'phone',
    'Site web': 'website',
    'Entreprise': 'company_name',
    'Organisation': 'organization_name',
    'LinkedIn': 'linkedin_url',
    'Facebook': 'facebook_url',
    'Instagram': 'instagram_url',
    'TikTok': 'tiktok_url',
    'X': 'x_url',
    'YouTube': 'youtube_url',
  };

  Map<String, TextEditingController> get _textEditors => {
    'first_name': _firstName,
    'last_name': _lastName,
    'bio': _bio,
    'profession': _profession,
    'city': _city,
    'address': _address,
    'phone': _phone,
    'website': _website,
    'company_name': _company,
    'organization_name': _organization,
    'linkedin_url': _linkedin,
    'facebook_url': _facebook,
    'instagram_url': _instagram,
    'tiktok_url': _tiktok,
    'x_url': _x,
    'youtube_url': _youtube,
  };

  void _setLocalError(String key, String? message) {
    if (!mounted) return;
    final updated = Map<String, String>.from(_fieldErrors);
    if (message == null) {
      updated.remove(key);
    } else {
      updated[key] = message;
    }
    setState(() {
      _checkedFields.add(key);
      _fieldErrors = updated;
      if (_error == 'Corrigez les champs indiqués.' && updated.isEmpty) {
        _error = null;
      }
    });
  }

  void _onTextChanged(String key, TextEditingController controller) {
    _rememberEdits();
    if (_checkedFields.contains(key) || _fieldErrors.containsKey(key)) {
      _setLocalError(key, PassportEditorFieldRules.error(key, controller.text));
    }
  }

  void _normalizeOnBlur(String key, TextEditingController controller) {
    if (!_loaded || _saving) return;
    final formatted = PassportEditorFieldRules.normalize(key, controller.text);
    if (formatted != controller.text) {
      controller.value = TextEditingValue(
        text: formatted,
        selection: TextSelection.collapsed(offset: formatted.length),
      );
      _rememberEdits();
    }
    _setLocalError(key, PassportEditorFieldRules.error(key, formatted));
  }

  Map<String, String> _validateBeforeSave() {
    final errors = <String, String>{};
    final baseline = _confirmedEditor;
    for (final entry in _textEditors.entries) {
      final key = entry.key;
      final controller = entry.value;
      final before = controller.text;
      // Don't change unrelated legacy values when saving one field.
      if (baseline != null && before == (baseline[key]?.toString() ?? '')) {
        continue;
      }
      final formatted = PassportEditorFieldRules.normalize(key, before);
      if (formatted != before) {
        controller.value = TextEditingValue(
          text: formatted,
          selection: TextSelection.collapsed(offset: formatted.length),
        );
        _rememberEdits();
      }
      final error = PassportEditorFieldRules.error(key, formatted);
      if (error != null) errors[key] = error;
    }
    final date = _birthDate.text.trim();
    if (date != (baseline?['birth_date']?.toString() ?? '')) {
      final error = PassportEditorFieldRules.error('birth_date', date);
      if (error != null) errors['birth_date'] = error;
    }
    if (_countryHasUnselectedInput ||
        (_country.text.trim().isNotEmpty && _selectedCountry == null)) {
      errors['country'] = 'Pays invalide.';
    }
    return errors;
  }

  void _rememberEdits() {
    _editRevision++;
    _edited = true;
    if (mounted && !_saving && _confirmation != null) {
      setState(() => _confirmation = null);
    }
    if (widget.drafts == null || !_loaded) return;
    // Only the newest editor snapshot is awaiting persistence. Per-keystroke
    // chains accumulate stale writes and delay the final draft at shutdown.
    _nextDraftSnapshot = Map<String, dynamic>.from(_currentEditor());
    if (_draftWorkerActive) return;
    _draftWorkerActive = true;
    _draftWrites = _flushLatestDraft();
  }

  Future<void> _flushLatestDraft() async {
    final drafts = widget.drafts;
    final profileId = widget.personal.store.profileId;
    Map<String, dynamic>? attempted;
    try {
      while (_nextDraftSnapshot != null && drafts != null) {
        final snapshot = _nextDraftSnapshot!;
        attempted = snapshot;
        _nextDraftSnapshot = null;
        await drafts.saveLocal(
          draftId: 'accounts-profile-editor-$profileId',
          owner: _draftOwner,
          resourceKind: _draftKind,
          resourceId: profileId,
          payload: snapshot,
        );
      }
    } on Object {
      // Keep the last unsaved snapshot available to a later edit/flush.
      _nextDraftSnapshot ??= attempted;
      if (mounted) {
        setState(
          () => _error =
              'Le brouillon local n’a pas pu être conservé sur cet appareil.',
        );
      }
    } finally {
      _draftWorkerActive = false;
    }
  }

  Future<void> _bootstrap() async {
    try {
      final snapshot = await widget.personal.store.readProjection(
        'personal.me',
      );
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
            _confirmedEditor = editor.payload;
            _applyEditor(editor.payload);
          }
          if (draft != null) {
            // Recover a pending local edit even when the previously confirmed
            // editor cache was unavailable or evicted.
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
      final account = response.jsonObject();
      final editor = _editorProjection(account);
      try {
        await _persistEditor(editor);
      } on Object {
        // A valid Accounts reply can still render if local storage is full.
      }
      if (!mounted) return;
      setState(() {
        // Never overwrite text entered while the background check was
        // pending. Those edits are not yet confirmed by the owner.
        _confirmedEditor = editor;
        _accountEmail = account['email']?.toString();
        _accountIdentifier = account['username']?.toString();
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
          _error = 'Impossible de charger les informations nécessaires à la modification.';
        }
      });
    }
  }

  Future<void> _changeIdentifier() async {
    if (_saving || !_loaded) return;
    final editor = TextEditingController(text: _accountIdentifier ?? '');
    String? localError;
    bool checked = false;
    try {
      final proposed = await showDialog<String>(
        context: context,
        builder: (route) => StatefulBuilder(
          builder: (dialog, update) => AlertDialog(
            title: const Text('Identifiant Makolo'),
            content: Focus(
              onFocusChange: (focused) {
                if (focused || !dialog.mounted) return;
                final normalized = PassportEditorFieldRules.normalize(
                  'username',
                  editor.text,
                );
                if (normalized != editor.text) {
                  editor.value = TextEditingValue(
                    text: normalized,
                    selection: TextSelection.collapsed(
                      offset: normalized.length,
                    ),
                  );
                }
                update(() {
                  checked = true;
                  localError = PassportEditorFieldRules.error(
                    'username',
                    normalized,
                  );
                });
              },
              child: TextField(
                controller: editor,
                autofocus: true,
                maxLength: 30,
                maxLengthEnforcement: MaxLengthEnforcement.none,
                autocorrect: false,
                enableSuggestions: false,
                textCapitalization: TextCapitalization.none,
                decoration: InputDecoration(
                  labelText: 'Nouvel identifiant',
                  prefixText: '@',
                  counterText: '',
                  errorText: localError,
                  suffixIcon:
                      checked &&
                          localError == null &&
                          editor.text.trim().isNotEmpty
                      ? const Icon(
                          Icons.check_circle_outline,
                          color: Colors.green,
                        )
                      : null,
                ),
                onChanged: (value) {
                  final result = PassportEditorFieldRules.error(
                    'username',
                    value,
                  );
                  if (checked || result == null) {
                    update(() {
                      checked = true;
                      localError = result;
                    });
                  }
                },
              ),
            ),
            actions: [
              MakoloActionButton(
                label: 'Annuler',
                appearance: MakoloActionAppearance.quiet,
                onPressed: () => Navigator.pop(dialog),
              ),
              FilledButton(
                onPressed: () {
                  final normalized = PassportEditorFieldRules.normalize(
                    'username',
                    editor.text,
                  );
                  final result = PassportEditorFieldRules.error(
                    'username',
                    normalized,
                  );
                  if (result != null) {
                    update(() {
                      checked = true;
                      localError = result;
                    });
                    return;
                  }
                  Navigator.pop(dialog, normalized);
                },
                child: const Text('Modifier'),
              ),
            ],
          ),
        ),
      );
      if (proposed == null ||
          proposed.isEmpty ||
          !mounted ||
          proposed == _accountIdentifier) {
        return;
      }
      try {
        final response = await widget.api.patch(
          'api/v1/accounts/auth/identifier/',
          body: {'username': proposed},
        );
        final user = response.jsonObject()['user'];
        final updated = user is Map ? user['username']?.toString() : null;
        if (!mounted) return;
        setState(() {
          _accountIdentifier = updated ?? proposed;
          _error = null;
          _confirmation = 'Identifiant Makolo mis à jour.';
        });
        try {
          await widget.personal.store.deleteProjection(
            'personal.me.passport',
            resourceKey: 'variant=complete',
          );
        } on Object {
          // Source owner projection will be fetched again on the next visit.
        }
        await _refreshPersonal();
      } on MakoloApiError catch (error) {
        if (!mounted) return;
        final errors = error.fields['username'];
        final reason = errors is List && errors.isNotEmpty
            ? errors.first.toString()
            : errors is String && errors.isNotEmpty
            ? errors
            : 'Impossible de modifier cet identifiant.';
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(reason)));
      } on Object {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Modification de l’identifiant indisponible.'),
          ),
        );
      }
    } finally {
      editor.dispose();
    }
  }

  /// Cheap photo checks before upload. Accounts validates the full image.
  Future<String?> _checkPickedPhoto(String path, String filename) async {
    const maxBytes = 5 * 1024 * 1024;
    final lower = filename.toLowerCase();
    final jpeg = lower.endsWith('.jpg') || lower.endsWith('.jpeg');
    final png = lower.endsWith('.png');
    final webp = lower.endsWith('.webp');
    if (!jpeg && !png && !webp) return 'Format de photo invalide.';
    try {
      final file = File(path);
      if (await file.length() > maxBytes) {
        return 'Photo trop volumineuse (5 Mo).';
      }
      final handle = await file.open();
      List<int> header;
      try {
        header = await handle.read(12);
      } finally {
        await handle.close();
      }
      bool at(int index, List<int> bytes) {
        if (header.length < index + bytes.length) return false;
        for (var i = 0; i < bytes.length; i++) {
          if (header[index + i] != bytes[i]) return false;
        }
        return true;
      }

      if (jpeg && !at(0, [0xFF, 0xD8, 0xFF]) ||
          png && !at(0, [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) ||
          webp &&
              !(at(0, [0x52, 0x49, 0x46, 0x46]) &&
                  at(8, [0x57, 0x45, 0x42, 0x50]))) {
        return 'Photo invalide.';
      }
    } on Object {
      return 'Photo inaccessible.';
    }
    return null;
  }

  Future<void> _changeAvatar() async {
    if (_saving || !_loaded) return;
    final source = await showModalBottomSheet<bool>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Column(
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
        ),
      ),
    );
    if (source == null || !mounted) return;
    try {
      final image = await ImagePickerSystemMediaPicker().pickImage(
        capture: source,
      );
      if (image == null || !mounted) return;
      final photoError = await _checkPickedPhoto(image.path, image.name);
      if (!mounted) return;
      if (photoError != null) {
        final errors = Map<String, String>.from(_fieldErrors);
        errors['avatar'] = photoError;
        setState(() => _fieldErrors = errors);
        return;
      }
      setState(() {
        final errors = Map<String, String>.from(_fieldErrors);
        errors.remove('avatar');
        _fieldErrors = errors;
      });
      final approved = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Modifier la photo'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ClipOval(
                child: Image.file(
                  File(image.path),
                  width: 152,
                  height: 152,
                  fit: BoxFit.cover,
                  errorBuilder: (_, _, _) => const Icon(Icons.person, size: 90),
                ),
              ),
              const SizedBox(height: 14),
              const Text('Utiliser cette photo sur mon passeport ?'),
            ],
          ),
          actions: [
            MakoloActionButton(
              label: 'Annuler',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => Navigator.pop(context, false),
            ),
            MakoloActionButton(
              label: 'Confirmer',
              appearance: MakoloActionAppearance.primary,
              onPressed: () => Navigator.pop(context, true),
            ),
          ],
        ),
      );
      if (approved != true || !mounted) return;
      setState(() {
        _saving = true;
        _error = null;
        _confirmation = null;
      });
      await widget.api.upload(
        'api/v1/accounts/auth/profile/update/',
        method: 'PATCH',
        files: [
          MakoloUploadFile(
            fieldName: 'avatar',
            path: image.path,
            filename: image.name,
            contentType: image.name.toLowerCase().endsWith('.png')
                ? 'image/png'
                : image.name.toLowerCase().endsWith('.webp')
                ? 'image/webp'
                : 'image/jpeg',
          ),
        ],
      );
      // Keep the confirmed portrait in the durable private file area, not OS
      // image cache. Owner projection refresh still reconciles the server fact.
      try {
        await ProfilePortraitStore(widget.personal.store.profileId)
            .savePickedFile(image.path);
      } on Object {
        // A later authenticated read can rehydrate the authorized portrait.
      }
      try {
        await widget.personal.store.deleteProjection(
          'personal.me.passport',
          resourceKey: 'variant=complete',
        );
      } on Object {
        // A later server read refreshes the owner projection.
      }
      final fresh = await _refreshPersonal();
      if (!mounted) return;
      setState(() {
        _saving = false;
        _confirmation = fresh
            ? 'Photo mise à jour.'
            : 'Photo enregistrée. Actualisation en attente.';
      });
    } on Object catch (error) {
      if (mounted) {
        final errors = Map<String, String>.from(_fieldErrors);
        errors['avatar'] = error is MakoloApiError && error.statusCode == 400
            ? 'Photo invalide.'
            : 'Photo non enregistrée.';
        setState(() {
          _saving = false;
          _fieldErrors = errors;
        });
      }
    }
  }

  Future<bool> _refreshPersonal() async {
    // Production uses the sole SyncEngine root source (actor validation,
    // tombstones, generatedAt monotonicity). The legacy injected-API path
    // remains only for standalone presentation/test hosts without a runtime.
    final engine = widget.sync;
    if (engine != null) return engine.refreshPersonalMe();
    try {
      final response = await widget.api.get('api/v1/me/');
      final envelope = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.me',
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
    final localErrors = _validateBeforeSave();
    if (localErrors.isNotEmpty) {
      setState(() {
        _fieldErrors = localErrors;
        _checkedFields.addAll(localErrors.keys);
        _error = 'Corrigez les champs indiqués.';
        _saveFailedRemotely = false;
        _confirmation = null;
      });
      return;
    }
    final submittedRevision = _editRevision;
    final confirmedEditor = _currentEditor();
    setState(() {
      _saving = true;
      _error = null;
      _saveFailedRemotely = false;
      _fieldErrors = const {};
      _confirmation = null;
    });
    // Send only changed fields. An unrelated legacy URL or phone number must
    // not cause a user-requested biography or birth-date change to fail.
    final baseline = _confirmedEditor;
    final changes = <String, dynamic>{
      for (final entry in confirmedEditor.entries)
        if (baseline == null || baseline[entry.key] != entry.value)
          entry.key: entry.value,
    };
    if (changes.isEmpty) {
      setState(() {
        _saving = false;
        _edited = false;
        _confirmation = 'Aucune modification à enregistrer.';
      });
      return;
    }
    try {
      await widget.api.patch(
        'api/v1/accounts/auth/profile/update/',
        body: changes,
      );
    } on Object catch (error) {
      if (!mounted) return;
      final validation = error is MakoloApiError && error.statusCode == 400;
      final fieldErrors = <String, String>{};
      if (validation) {
        for (final entry in error.fields.entries) {
          String? readable(Object? value) {
            if (value is String && value.trim().isNotEmpty) return value.trim();
            if (value is List && value.isNotEmpty) {
              return value.map((v) => v.toString()).join(' · ');
            }
            return null;
          }

          final message = readable(entry.value);
          if (message != null) fieldErrors[entry.key] = message;
        }
      }
      setState(() {
        _saving = false;
        _fieldErrors = fieldErrors;
        _saveFailedRemotely = !validation || fieldErrors.isEmpty;
        _error = validation && fieldErrors.isNotEmpty
            ? 'Corrigez les champs indiqués.'
            : error is MakoloTransportError
            ? 'Connexion indisponible. Les modifications sont conservées.'
            : error is MakoloApiError && error.statusCode == 401
            ? 'Connexion expirée. Reconnectez-vous pour enregistrer.'
            : 'Enregistrement impossible. Vos modifications sont conservées.';
      });
      return;
    }

    _confirmedEditor = confirmedEditor;
    // Accounts confirmed these fields. Clear the device-owned draft only
    // after the last local write has completed.
    try {
      await _persistEditor(confirmedEditor);
    } on Object {
      // The remote success is not undone by a local storage failure.
    }
    try {
      await _draftWrites;
      if (submittedRevision == _editRevision &&
          _nextDraftSnapshot == null &&
          !_draftWorkerActive) {
        await widget.drafts?.delete(
          owner: _draftOwner,
          resourceKind: _draftKind,
          resourceId: widget.personal.store.profileId,
        );
      }
    } on Object {
      // An already-confirmed owner mutation remains confirmed.
    }
    if (submittedRevision == _editRevision) _edited = false;
    // The Passport's one-shot local source is now stale. Invalidate it only
    // after Accounts has confirmed the mutation; do not wipe offline facts
    // on a failed save.
    try {
      await widget.personal.store.deleteProjection(
        'personal.me.passport',
        resourceKey: 'variant=complete',
      );
    } on Object {
      // A later authenticated owner read still reconciles the cache.
    }
    final refreshed = await _refreshPersonal();
    if (!mounted) return;
    setState(() {
      _saving = false;
      _confirmation = submittedRevision != _editRevision
          ? 'Les modifications envoyées sont enregistrées. '
                'Vos changements plus récents restent à enregistrer.'
          : refreshed
          ? 'Modifications enregistrées.'
          : 'Enregistré. Actualisation en attente.';
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    for (final controller in [
      _firstName,
      _lastName,
      _birthDate,
      _profession,
      _city,
      _country,
      _bio,
      _phone,
      _website,
      _linkedin,
      _facebook,
      _instagram,
      _tiktok,
      _x,
      _youtube,
      _company,
      _organization,
      _address,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.focusVisibility && _loaded && !_visibilityJumpScheduled) {
      _visibilityJumpScheduled = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        final anchor = _visibilityAnchor.currentContext;
        if (anchor != null) {
          Scrollable.ensureVisible(
            anchor,
            duration: const Duration(milliseconds: 220),
            alignment: 0.12,
          );
        } else if (_scrollController.hasClients) {
          _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
        }
      });
    }
    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.focusVisibility
              ? 'Confidentialité du Profil'
              : 'Modifier le Passeport',
        ),
      ),
      body: _loading && _cachedIdentity == null
          ? const Center(child: CircularProgressIndicator.adaptive())
          : !_loaded
          ? _localSummary(context)
          : ListView(
              controller: _scrollController,
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
              children: [
                if (_error != null) ...[
                  Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (!_saving && _saveFailedRemotely)
                    MakoloActionButton(
                      label: 'Réessayer l’enregistrement',
                      appearance: MakoloActionAppearance.quiet,
                      onPressed: _save,
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
                _readOnlyAccountDetail(
                  'Identifiant Makolo',
                  _accountIdentifier ??
                      _cachedIdentity?['username']?.toString(),
                  onChange: _saving ? null : _changeIdentifier,
                ),
                _birthDatePicker(),
                _genderSelector(),
                _field('À propos', _bio, lines: 3),
                MakoloActionButton(
                  label: 'Modifier la photo',
                  onPressed: _saving ? null : _changeAvatar,
                  appearance: MakoloActionAppearance.secondary,
                  icon: Icons.photo_camera_outlined,
                ),
                if (_fieldErrors['avatar'] != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      _fieldErrors['avatar']!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ),
                const SizedBox(height: 12),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  initiallyExpanded: [
                    _city.text,
                    _country.text,
                    _address.text,
                  ].any((value) => value.trim().isNotEmpty),
                  title: const Text('Localisation'),
                  children: [
                    _countryAutocomplete(),
                    _field('Ville', _city),
                    _field('Adresse', _address),
                  ],
                ),
                _sectionTitle('Contact'),
                _readOnlyAccountDetail('Adresse e-mail', _accountEmail),
                _field('Téléphone', _phone),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  initiallyExpanded: [
                    _profession.text,
                    _company.text,
                    _organization.text,
                  ].any((value) => value.trim().isNotEmpty),
                  title: const Text('Activité professionnelle'),
                  children: [
                    _field('Profession', _profession),
                    _field('Entreprise', _company),
                    _field('Organisation', _organization),
                  ],
                ),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  initiallyExpanded: [
                    _website.text,
                    _linkedin.text,
                    _facebook.text,
                    _instagram.text,
                    _tiktok.text,
                    _x.text,
                    _youtube.text,
                  ].any((value) => value.trim().isNotEmpty),
                  title: const Text('Liens et réseaux sociaux'),
                  children: [
                    _field('Site web', _website),
                    _field('LinkedIn', _linkedin),
                    _field('Facebook', _facebook),
                    _field('Instagram', _instagram),
                    _field('TikTok', _tiktok),
                    _field('X', _x),
                    _field('YouTube', _youtube),
                  ],
                ),
                KeyedSubtree(
                  key: _visibilityAnchor,
                  child: _sectionTitle('Visibilité générale'),
                ),
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Passeport public'),
                  value: _publicProfile,
                  onChanged: _saving
                      ? null
                      : (value) => setState(() {
                          _publicProfile = value;
                          _rememberEdits();
                        }),
                ),
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Visible dans la recherche'),

                  value: _searchable,
                  onChanged: _saving
                      ? null
                      : (value) => setState(() {
                          _searchable = value;
                          _rememberEdits();
                        }),
                ),
                const SizedBox(height: 20),
                MakoloActionButton(
                  key: const Key('me-profile-save-action'),
                  label: _saving ? 'Enregistrement…' : 'Enregistrer',
                  icon: Icons.check_rounded,
                  onPressed: _saving ? null : _save,
                  appearance: MakoloActionAppearance.primary,
                  phase: _saving
                      ? MakoloActionPhase.processing
                      : _error != null
                      ? MakoloActionPhase.failed
                      : _confirmation != null && !_edited
                      ? MakoloActionPhase.confirmed
                      : MakoloActionPhase.available,
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
              ? 'Informations du profil indisponibles hors ligne.'
              : 'Dernières informations enregistrées. Connexion requise pour modifier.',
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
          child: MakoloActionButton(
            label: 'Réessayer',
            appearance: MakoloActionAppearance.quiet,
            icon: Icons.refresh_rounded,
            onPressed: _read,
          ),
        ),
      ],
    );
  }

  Widget _readOnlyAccountDetail(
    String label,
    String? value, {
    VoidCallback? onChange,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: InputDecorator(
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              value == null || value.trim().isEmpty
                  ? 'Non disponible'
                  : value.trim(),
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
          if (onChange != null)
            MakoloIconActionButton(
              tooltip: 'Modifier $label',
              onPressed: onChange,
              icon: Icons.edit_outlined,
            ),
        ],
      ),
    ),
  );

  Widget _sectionTitle(String title) => Padding(
    padding: const EdgeInsets.only(top: 18, bottom: 12),
    child: Text(
      title,
      style: Theme.of(context).textTheme.titleMedium
          ?.copyWith(fontWeight: FontWeight.w700),
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
        return makoloCountries.where(
          (country) =>
              country.label.toLowerCase().contains(query) ||
              country.code.toLowerCase().startsWith(query),
        );
      },
      onSelected: (country) {
        setState(() {
          _selectedCountry = country;
          _country.text = country.code;
          _countryHasUnselectedInput = false;
          _checkedFields.add('country');
          final errors = Map<String, String>.from(_fieldErrors);
          errors.remove('country');
          _fieldErrors = errors;
        });
        _rememberEdits();
      },
      fieldViewBuilder: (context, controller, focusNode, onFieldSubmitted) =>
          Focus(
            onFocusChange: (focused) {
              if (focused) return;
              final match = countryForValue(controller.text);
              if (match != null) {
                if (_selectedCountry?.code != match.code) {
                  _country.text = match.code;
                  _rememberEdits();
                }
                controller.value = TextEditingValue(
                  text: match.label,
                  selection: TextSelection.collapsed(
                    offset: match.label.length,
                  ),
                );
              } else if (controller.text.trim().isEmpty) {
                _country.clear();
              }
              if (!mounted) return;
              setState(() {
                _selectedCountry = match;
                _countryHasUnselectedInput =
                    match == null && controller.text.trim().isNotEmpty;
                _checkedFields.add('country');
                final errors = Map<String, String>.from(_fieldErrors);
                if (_countryHasUnselectedInput) {
                  errors['country'] = 'Pays invalide.';
                } else {
                  errors.remove('country');
                }
                _fieldErrors = errors;
              });
            },
            child: TextFormField(
              controller: controller,
              focusNode: focusNode,
              textCapitalization: TextCapitalization.words,
              decoration: InputDecoration(
                labelText: 'Pays',
                errorText: _fieldErrors['country'],
                hintText: 'Rechercher un pays',
                prefixIcon: const Icon(Icons.public_outlined),
                suffixIcon:
                    _checkedFields.contains('country') &&
                        _fieldErrors['country'] == null &&
                        _selectedCountry != null
                    ? const Icon(
                        Icons.check_circle_outline,
                        color: Colors.green,
                      )
                    : null,
                border: const OutlineInputBorder(),
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 15,
                ),
              ),
              onChanged: (value) {
                final match = countryForValue(value);
                _selectedCountry = match;
                _country.text = match?.code ?? '';
                _countryHasUnselectedInput =
                    match == null && value.trim().isNotEmpty;
                _rememberEdits();
                if (_checkedFields.contains('country') ||
                    _fieldErrors.containsKey('country')) {
                  _setLocalError(
                    'country',
                    _countryHasUnselectedInput ? 'Pays invalide.' : null,
                  );
                }
              },
              onFieldSubmitted: (_) => onFieldSubmitted(),
            ),
          ),
    ),
  );

  Widget _birthDatePicker() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextFormField(
        controller: _birthDate,
        readOnly: true,
        decoration: InputDecoration(
          labelText: 'Date de naissance',
          errorText: _fieldErrors['birth_date'],
          hintText: 'Facultatif',
          border: const OutlineInputBorder(),
          suffixIcon: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (_birthDate.text.isNotEmpty)
                IconButton(
                  tooltip: 'Effacer la date de naissance',
                  onPressed: _saving
                      ? null
                      : () => setState(() {
                          _birthDate.clear();
                          _rememberEdits();
                        }),
                  icon: const Icon(Icons.close),
                ),
              const Icon(Icons.calendar_month_outlined),
              const SizedBox(width: 10),
            ],
          ),
        ),
        onTap: _saving
            ? null
            : () async {
                final today = DateTime.now();
                final existing = DateTime.tryParse(_birthDate.text);
                final selected = await showDatePicker(
                  context: context,
                  initialDate: existing != null && !existing.isAfter(today)
                      ? existing
                      : DateTime(today.year - 18, today.month, today.day),
                  firstDate: DateTime(1900),
                  lastDate: today,
                );
                if (selected == null || !mounted) return;
                setState(() {
                  _birthDate.text =
                      '${selected.year.toString().padLeft(4, '0')}-'
                      '${selected.month.toString().padLeft(2, '0')}-'
                      '${selected.day.toString().padLeft(2, '0')}';
                  _rememberEdits();
                });
              },
      ),
    );
  }

  Widget _genderSelector() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: DropdownButtonFormField<String>(
        key: ValueKey('gender-$_gender'),
        initialValue: _gender,
        decoration: InputDecoration(
          labelText: 'Genre',
          errorText: _fieldErrors['gender'],
          border: OutlineInputBorder(),
        ),
        items: const [
          DropdownMenuItem(value: 'unspecified', child: Text('Non renseigné')),
          DropdownMenuItem(value: 'female', child: Text('Femme')),
          DropdownMenuItem(value: 'male', child: Text('Homme')),
        ],
        onChanged: _saving
            ? null
            : (value) {
                if (value == null) return;
                setState(() {
                  _gender = value;
                  _rememberEdits();
                });
              },
      ),
    );
  }

  Widget _field(
    String label,
    TextEditingController controller, {
    int lines = 1,
  }) {
    final key = _fieldKeys[label]!;
    final link = PassportEditorFieldRules.isLink(key);
    final phone = key == 'phone';
    final name = key == 'first_name' || key == 'last_name';
    final multiLine = lines > 1 || key == 'address';
    final checked = _checkedFields.contains(key);
    final error = _fieldErrors[key];
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Focus(
        onFocusChange: (focused) {
          if (!focused) _normalizeOnBlur(key, controller);
        },
        child: TextField(
          controller: controller,
          onChanged: (_) => _onTextChanged(key, controller),
          maxLines: multiLine ? (lines > 1 ? lines : 2) : 1,
          maxLength: PassportEditorFieldRules.maxLengths[key],
          maxLengthEnforcement: MaxLengthEnforcement.none,
          keyboardType: phone
              ? TextInputType.phone
              : link
              ? TextInputType.url
              : name
              ? TextInputType.name
              : multiLine
              ? TextInputType.multiline
              : TextInputType.text,
          textCapitalization: phone || link
              ? TextCapitalization.none
              : name || key == 'city'
              ? TextCapitalization.words
              : TextCapitalization.sentences,
          autocorrect: !phone && !link,
          enableSuggestions: !phone && !link,
          decoration: InputDecoration(
            labelText: label,
            errorText: error,
            counterText: '',
            suffixIcon:
                checked && error == null && controller.text.trim().isNotEmpty
                ? const Icon(Icons.check_circle_outline, color: Colors.green)
                : null,
            border: const OutlineInputBorder(),
            isDense: true,
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 14,
              vertical: 15,
            ),
          ),
        ),
      ),
    );
  }
}
