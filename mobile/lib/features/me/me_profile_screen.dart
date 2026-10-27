import 'package:flutter/material.dart';

import '../../network/makolo_api_client.dart';
import '../../platform/camera/system_media_picker.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/projection_contract.dart';

/// Self-profile editor backed by the existing Accounts owner API.
class MeProfileScreen extends StatefulWidget {
  const MeProfileScreen({super.key, required this.api, required this.personal,
    this.openAvatarPicker = false});
  final MakoloApiClient api;
  final PersonalRepository personal;
  final bool openAvatarPicker;

  @override
  State<MeProfileScreen> createState() => _MeProfileScreenState();
}

class _MeProfileScreenState extends State<MeProfileScreen> {
  final _firstName = TextEditingController();
  final _lastName = TextEditingController();
  final _profession = TextEditingController();
  final _city = TextEditingController();
  final _country = TextEditingController();
  final _bio = TextEditingController();

  bool _avatarPickerScheduled = false;
  bool _loading = true;
  bool _loaded = false;
  bool _saving = false;
  String? _error;
  String? _confirmation;

  @override
  void initState() {
    super.initState();
    _read();
  }

  Future<void> _read() async {
    try {
      final response = await widget.api.get('api/v1/accounts/auth/me/');
      final user = response.jsonObject();
      final profile = user['profile'];
      final fields = profile is Map ? profile : const <String, dynamic>{};
      if (!mounted) return;
      setState(() {
        _firstName.text = user['first_name']?.toString() ?? '';
        _lastName.text = user['last_name']?.toString() ?? '';
        _bio.text = user['bio']?.toString() ?? '';
        _profession.text = fields['profession']?.toString() ?? '';
        _city.text = fields['city']?.toString() ?? '';
        _country.text = fields['country']?.toString() ?? '';
        _loading = false;
        _loaded = true;
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
        _error = 'Profil momentanément indisponible.';
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
          content: const Text('Utiliser cette photo sur mon profil ?'),
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
      final fresh = await _refreshPersonal();
      if (!mounted) return;
      setState(() {
        _saving = false;
        _confirmation = fresh
            ? 'Photo mise à jour.'
            : 'Photo enregistrée. Actualisation en attente.';
      });
    } on Object {
      if (mounted) setState(() {
        _saving = false;
        _error = 'Impossible de modifier la photo.';
      });
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
          'country': _country.text.trim(),
          'bio': _bio.text.trim(),
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

    // The Accounts owner confirmed the change. Refresh the sole personal.me
    // projection rather than locally inventing a definitive new identity.
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
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mon profil')),
      body: _loading
          ? const Center(child: CircularProgressIndicator.adaptive())
          : !_loaded
          ? Center(
              child: TextButton.icon(
                onPressed: _read,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Réessayer'),
              ),
            )
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
                _field('Prénom', _firstName),
                _field('Nom', _lastName),
                _field('Profession', _profession),
                _field('Ville', _city),
                _field('Pays', _country),
                _field('À propos', _bio, lines: 4),
                OutlinedButton.icon(
                  onPressed: _saving ? null : _changeAvatar,
                  icon: const Icon(Icons.photo_camera_outlined),
                  label: const Text('Modifier la photo'),
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

  Widget _field(
    String label,
    TextEditingController controller, {
    int lines = 1,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: TextField(
      controller: controller,
      maxLines: lines,
      textCapitalization: TextCapitalization.sentences,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
    ),
  );
}
