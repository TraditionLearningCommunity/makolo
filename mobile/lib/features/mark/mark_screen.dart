import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/files/profile_file_store.dart';
import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';
import '../../navigation/avatar_sheet.dart';
import '../../navigation/shell_header.dart';
import '../../navigation/space_context_bar.dart';
import '../../platform/camera/system_media_picker.dart';
import '../../platform/files/native_file_acquisition.dart';
import '../../platform/files/system_file_picker.dart';
import '../../platform/permissions/permission_gateway.dart';
import 'mark_repository.dart';

class MarkScreen extends StatefulWidget {
  const MarkScreen({super.key, required this.runtime, this.selectedContext});
  final AppRuntime runtime;
  final Map<String, String>? selectedContext;

  @override
  State<MarkScreen> createState() => _MarkScreenState();
}

class _MarkScreenState extends State<MarkScreen> {
  late final TextEditingController _input;
  late final MarkRepository _repository;
  ActorContext _actor = const PersonalActorContext();
  MarkResult? _result;
  bool _busy = false;
  bool _restoring = true;
  List<Map<String, dynamic>> _attachments = const [];
  Map<String, String>? _selectedContext;
  NativeFileAcquisitionCoordinator? _files;

  @override
  void initState() {
    super.initState();
    _input = TextEditingController();
    _repository = MarkRepository(widget.runtime);
    widget.runtime.actorContext?.addListener(_onActorChanged);
    _actor = widget.runtime.actorContext?.value ?? const PersonalActorContext();
    _selectedContext = widget.selectedContext;
    _restoreDraft();
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    _input.dispose();
    super.dispose();
  }

  void _onActorChanged() {
    final actor = widget.runtime.actorContext?.value;
    if (actor == null || actor == _actor) return;
    setState(() {
      _actor = actor;
      _result = null;
      _attachments = const [];
      _selectedContext = widget.selectedContext;
      _restoring = true;
    });
    _input.clear();
    _restoreDraft();
  }

  Future<void> _restoreDraft() async {
    final draft = await _repository.readDraft(_actor);
    if (!mounted) return;
    if (draft != null) {
      _input.text = draft['input']?.toString() ?? '';
      final rawSelected = draft['selected'];
      if (_selectedContext == null && rawSelected is Map) {
        _selectedContext = {
          for (final entry in rawSelected.entries)
            if (entry.key is String && entry.value is String)
              entry.key as String: entry.value as String,
        };
      }
      final raw = draft['attachments'];
      if (raw is List) {
        _attachments = [
          for (final item in raw)
            if (item is Map)
              {
                for (final entry in item.entries)
                  if (entry.key is String) entry.key as String: entry.value,
              },
        ];
      }
    }
    setState(() => _restoring = false);
  }

  Future<NativeFileAcquisitionCoordinator?> _fileCoordinator() async {
    if (_files != null) return _files;
    final database = widget.runtime.database;
    final profileId = widget.runtime.session?.profileId;
    if (database == null || profileId == null) return null;
    final store = await ProfileFileStore.open(
      database: database,
      profileId: profileId,
    );
    _files = NativeFileAcquisitionCoordinator(
      store: store,
      permissions: const PermissionHandlerGateway(),
      mediaPicker: ImagePickerSystemMediaPicker(),
      filePicker: const NativeSystemFilePicker(),
    );
    return _files;
  }

  Future<void> _pickFiles() async {
    final coordinator = await _fileCoordinator();
    if (coordinator == null) {
      _show('Les pièces jointes locales ne sont pas disponibles dans cette session.');
      return;
    }
    final result = await coordinator.pickFiles(
      owner: _owner,
      purpose: 'mark_intake',
      fileIdFor: (index, file) =>
          'mark-' +
          DateTime.now().microsecondsSinceEpoch.toString() +
          '-' +
          index.toString(),
    );
    if (!mounted) return;
    if (!result.acquired) {
      _show('Aucune pièce jointe n’a été ajoutée.');
      return;
    }
    setState(() {
      _attachments = [
        ..._attachments,
        ...result.files.map(
          (file) => {
            'file_id': file.fileId,
            'name': file.path.split('/').last,
            'purpose': file.purpose,
          },
        ),
      ];
    });
    await _saveDraft();
  }

  Future<void> _capturePhoto() async {
    final coordinator = await _fileCoordinator();
    if (coordinator == null) {
      _show('La capture photo locale n’est pas disponible dans cette session.');
      return;
    }
    final result = await coordinator.capturePhoto(
      fileId: 'mark-photo-' + DateTime.now().microsecondsSinceEpoch.toString(),
      owner: _owner,
      purpose: 'mark_intake',
    );
    if (!mounted) return;
    if (!result.acquired) {
      _show('La photo n’a pas été capturée.');
      return;
    }
    setState(() {
      _attachments = [
        ..._attachments,
        {
          'file_id': result.files.single.fileId,
          'name': result.files.single.path.split('/').last,
          'purpose': result.files.single.purpose,
          'kind': 'photo',
        },
      ];
    });
    await _saveDraft();
  }

  String get _owner => switch (_actor) {
    PersonalActorContext() => 'profile',
    SpaceActorContext(:final space) => 'space:' + space.slug,
  };

  Future<void> _saveDraft() => _repository.saveDraft(
    actor: _actor,
    input: _input.text,
    inputKind: _attachments.isEmpty ? 'text' : 'document',
    attachments: _attachments,
    selected: _selectedContext,
  );

  Future<void> _submit() async {
    if (_busy) return;
    final input = _input.text.trim();
    if (input.isEmpty && _attachments.isEmpty) {
      _show('Dites simplement ce que vous voulez donner à Makolo.');
      return;
    }
    setState(() => _busy = true);
    final result = await _repository.submit(
      actor: _actor,
      input: input,
      inputKind: _attachments.isEmpty ? 'text' : 'document',
      attachments: _attachments,
      selected: _selectedContext,
    );
    if (!mounted) return;
    setState(() {
      _busy = false;
      _result = result;
    });
  }

  void _show(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final actor = _actor;
    return Scaffold(
      appBar: MakoloPrimaryHeader(
        kind: MakoloHeaderKind.mark,
        onAvatar: () => showMakoloAvatarSheet(context, runtime: widget.runtime),
      ),
      body: SafeArea(
        top: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 32),
          children: [
            if (actor is SpaceActorContext)
              MakoloSpaceContextBar(runtime: widget.runtime, actor: actor),
            const SizedBox(height: 18),
            const Center(child: MakoloMark(size: 56)),
            const SizedBox(height: 24),
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 720),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'Qu’est-ce que vous avez en tête ?',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Dites-le comme vous le diriez à quelqu’un.',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 20),
                    TextField(
                      controller: _input,
                      minLines: 7,
                      maxLines: 12,
                      maxLength: 600,
                      textInputAction: TextInputAction.newline,
                      decoration: const InputDecoration(
                        hintText: 'Ex. Retrouve mon billet pour ce soir',
                        alignLabelWithHint: true,
                      ),
                      onChanged: (_) => _saveDraft(),
                    ),
                    if (_selectedContext != null || _attachments.isNotEmpty) ...[
                      if (_selectedContext != null)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Text(
                            'Contexte sélectionné : ' + (_selectedContext!['kind'] ?? 'réalité'),
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final item in _attachments)
                            Chip(
                              avatar: const Icon(Icons.attach_file, size: 18),
                              label: Text(item['name']?.toString() ?? 'Pièce'),
                            ),
                        ],
                      ),
                    ],
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        OutlinedButton.icon(
                          onPressed: _busy ? null : _pickFiles,
                          icon: const Icon(Icons.attach_file),
                          label: const Text('Joindre'),
                        ),
                        OutlinedButton.icon(
                          onPressed: _busy ? null : _capturePhoto,
                          icon: const Icon(Icons.photo_camera_outlined),
                          label: const Text('Photo'),
                        ),
                        OutlinedButton.icon(
                          onPressed: _busy
                              ? null
                              : () => _show(
                                    'La voix sera disponible lorsque la capability de transcription sera exposée.',
                                  ),
                          icon: const Icon(Icons.mic_none),
                          label: const Text('Voix'),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    FilledButton(
                      onPressed: _busy || _restoring ? null : _submit,
                      child: Text(_busy ? 'Envoi…' : 'Continuer'),
                    ),
                    if (_restoring)
                      const Padding(
                        padding: EdgeInsets.only(top: 12),
                        child: Text('Restauration du brouillon…'),
                      ),
                    if (_result != null) ...[
                      const SizedBox(height: 24),
                      _MarkResultView(result: _result!),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MarkResultView extends StatelessWidget {
  const _MarkResultView({required this.result});
  final MarkResult result;

  @override
  Widget build(BuildContext context) {
    final question = result.question;
    final action = result.action;
    final handoff = result.handoff;
    final label = switch (result.state) {
      'needs_clarification' => 'Précision nécessaire',
      'needs_confirmation' => 'Confirmation nécessaire',
      'offline_draft' => 'Brouillon local',
      'completed' => 'Terminé',
      'forbidden' => 'Action non autorisée',
      'unsupported' => 'Pas encore disponible',
      'unknown' => 'À préciser',
      'failed' => 'Échec',
      _ => 'Makolo',
    };

    return Semantics(
      liveRegion: true,
      label: label,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: Theme.of(context).textTheme.titleMedium),
              if (result.message != null) ...[
                const SizedBox(height: 8),
                Text(result.message!),
              ],
              if (question?['summary'] != null) ...[
                const SizedBox(height: 12),
                Text(question!['summary'].toString()),
              ],
              if (question?['options'] is List)
                for (final option in question!['options'] as List)
                  if (option is Map)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(option['label']?.toString() ?? ''),
                    ),
              if (action?['consequence'] != null) ...[
                const SizedBox(height: 12),
                Text(action!['consequence'].toString()),
              ],
              if (handoff?['surface'] != null) ...[
                const SizedBox(height: 12),
                Text('Suite : ' + handoff!['surface'].toString()),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
