import 'dart:async';
import 'dart:io';
import 'dart:math';

import 'package:flutter/foundation.dart'
    show mapEquals, kIsWeb, defaultTargetPlatform, TargetPlatform;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path/path.dart' as p;
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/files/profile_file_store.dart';
import '../../data/local/profile_store.dart';
import '../../design/action_controls.dart';
import '../../design/makolo_mark.dart';
import '../../navigation/avatar_sheet.dart';
import '../../navigation/destination.dart';
import '../../navigation/shell_header.dart';
import '../../navigation/space_context_bar.dart';
import '../../platform/camera/system_media_picker.dart';
import '../../platform/files/native_file_acquisition.dart';
import '../../platform/files/system_file_picker.dart';
import '../../platform/permissions/permission_gateway.dart';
import '../../platform/sharing/shared_payload_coordinator.dart';
import '../../platform/sharing/system_share_receiver.dart';
import '../../runtime/runtime_ingress.dart';
import '../../runtime/runtime_providers.dart';
import 'mark_dictation_capture.dart';
import 'mark_navigation.dart';
import 'mark_repository.dart';
import 'mark_voice_capture.dart';

class MarkScreen extends StatefulWidget {
  const MarkScreen({
    super.key,
    required this.runtime,
    this.selectedContext,
    this.onSwitchAccount,
    this.onLogout,
  });
  final AppRuntime runtime;
  final VoidCallback? onSwitchAccount;
  final VoidCallback? onLogout;
  final Map<String, String>? selectedContext;

  @override
  State<MarkScreen> createState() => _MarkScreenState();
}

class _MarkScreenState extends State<MarkScreen> {
  late final TextEditingController _input;
  final FocusNode _inputFocus = FocusNode();
  late MarkRepository _repository;
  int _draftRevision = 0;
  ActorContext _actor = const PersonalActorContext();
  MarkResult? _result;
  bool _busy = false;
  bool _restoring = true;
  List<Map<String, dynamic>> _attachments = const [];
  List<String> _links = const [];
  Map<String, String>? _selectedContext;
  NativeFileAcquisitionCoordinator? _files;
  ProfileFileStore? _voiceStore;
  bool _voiceCapture = false;
  bool _dictating = false;
  String? _pendingConfirmationCode;
  String? _pendingConfirmationKey;
  Stream<StoredProjection?>? _meStream;
  RuntimeIngress? _ingress;
  StreamSubscription<void>? _shareSubscription;
  bool _processingShare = false;

  @override
  void initState() {
    super.initState();
    _input = TextEditingController();
    _repository = MarkRepository(widget.runtime);
    _meStream = widget.runtime.personal?.watchMe();
    widget.runtime.actorContext?.addListener(_onActorChanged);
    _actor = widget.runtime.actorContext?.value ?? const PersonalActorContext();
    _selectedContext = widget.selectedContext;
    _restoreDraft();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final next = ProviderScope.containerOf(context)
        .read(runtimeIngressProvider);
    if (identical(next, _ingress)) return;
    _shareSubscription?.cancel();
    _ingress = next;
    _shareSubscription = next?.sharesChanged.listen((_) {
      unawaited(_drainSharedInputs());
    });
    unawaited(_drainSharedInputs());
  }

  @override
  void didUpdateWidget(covariant MarkScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.runtime, widget.runtime)) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      widget.runtime.actorContext?.addListener(_onActorChanged);
      _draftRevision++;
      _repository = MarkRepository(widget.runtime);
      _files = null;
      _actor =
          widget.runtime.actorContext?.value ?? const PersonalActorContext();
      _result = null;
      _attachments = const [];
      _links = const [];
      _voiceCapture = false;
      _dictating = false;
      _voiceStore = null;
      _pendingConfirmationCode = null;
      _pendingConfirmationKey = null;
      _selectedContext = widget.selectedContext;
      _restoring = true;
      _busy = false;
      _input.clear();
      _meStream = widget.runtime.personal?.watchMe();
      unawaited(_restoreDraft());
    } else {
      if (oldWidget.runtime.personal != widget.runtime.personal) {
        _meStream = widget.runtime.personal?.watchMe();
      }
      if (!mapEquals(oldWidget.selectedContext, widget.selectedContext)) {
        _selectedContext = widget.selectedContext;
        _result = null;
        unawaited(_saveDraft());
      }
    }
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    _shareSubscription?.cancel();
    _input.dispose();
    _inputFocus.dispose();
    super.dispose();
  }

  void _onActorChanged() {
    final actor = widget.runtime.actorContext?.value;
    if (actor == null || actor == _actor) return;
    _draftRevision++;
    setState(() {
      _actor = actor;
      _result = null;
      _attachments = const [];
      _links = const [];
      _voiceCapture = false;
      _dictating = false;
      _voiceStore = null;
      _pendingConfirmationCode = null;
      _pendingConfirmationKey = null;
      _selectedContext = widget.selectedContext;
      _restoring = true;
      _busy = false;
    });
    _input.clear();
    _restoreDraft();
  }

  Future<void> _restoreDraft() async {
    final revision = _draftRevision;
    final actor = _actor;
    final repository = _repository;
    final draft = await repository.readDraft(actor);
    if (!mounted ||
        revision != _draftRevision ||
        repository != _repository ||
        actor != _actor) {
      return;
    }
    if (draft != null) {
      _pendingConfirmationCode = draft['pending_confirmation_code']?.toString();
      _pendingConfirmationKey = draft['pending_confirmation_key']?.toString();
      _input.text = draft['input']?.toString() ?? '';
      final rawSelected = draft['selected'];
      if (_selectedContext == null && rawSelected is Map) {
        _selectedContext = {
          for (final entry in rawSelected.entries)
            if (entry.key is String && entry.value is String)
              entry.key as String: entry.value as String,
        };
      }
      final rawLinks = draft['links'];
      if (rawLinks is List) {
        _links = [
          for (final link in rawLinks)
            if (link is String && _isSafeLink(link)) link,
        ];
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
    unawaited(_drainSharedInputs());
  }

  Future<NativeFileAcquisitionCoordinator?> _fileCoordinator() async {
    if (_files != null) return _files;
    final database = widget.runtime.database;
    final profileId = widget.runtime.session?.profileId;
    if (database == null || profileId == null) return null;
    final runtime = widget.runtime;
    final store = await ProfileFileStore.open(
      database: database,
      profileId: profileId,
    );
    if (!mounted || !identical(runtime, widget.runtime)) return null;
    _files = NativeFileAcquisitionCoordinator(
      store: store,
      permissions: const PermissionHandlerGateway(),
      mediaPicker: ImagePickerSystemMediaPicker(),
      filePicker: const NativeSystemFilePicker(),
    );
    return _files;
  }

  bool _isSafeLink(String raw) {
    if (raw.isEmpty || raw.length > 2048) return false;
    final uri = Uri.tryParse(raw);
    return uri != null &&
        (uri.scheme == 'https' || uri.scheme == 'http') &&
        uri.host.isNotEmpty &&
        uri.userInfo.isEmpty;
  }

  Future<void> _addLink() async {
    final revision = _draftRevision;
    final controller = TextEditingController();
    var accepted = false;
    final link = await showDialog<String>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, refresh) => AlertDialog(
          title: const Text('Ajouter un lien'),
          content: TextField(
            key: const ValueKey('mark-url-input'),
            controller: controller,
            autofocus: true,
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: const InputDecoration(hintText: 'https://…'),
            onChanged: (value) =>
                refresh(() => accepted = _isSafeLink(value.trim())),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Annuler'),
            ),
            TextButton(
              onPressed: accepted
                  ? () => Navigator.pop(dialogContext, controller.text.trim())
                  : null,
              child: const Text('Ajouter'),
            ),
          ],
        ),
      ),
    );
    controller.dispose();
    if (!mounted || revision != _draftRevision || link == null) return;
    if (!_isSafeLink(link) || _links.contains(link)) return;
    setState(() => _links = [..._links, link]);
    await _saveDraft();
  }

  Future<void> _removeLink(String link) async {
    setState(
      () => _links = [
        for (final item in _links)
          if (item != link) item,
      ],
    );
    await _saveDraft();
  }

  Future<void> _drainSharedInputs() async {
    if (_processingShare ||
        _restoring ||
        _busy ||
        _voiceCapture ||
        _dictating ||
        !mounted ||
        widget.runtime.drafts == null) {
      return;
    }
    final ingress = _ingress;
    final profileId = widget.runtime.session?.profileId;
    if (ingress == null ||
        !ingress.hasPendingShare ||
        profileId == null ||
        profileId.isEmpty) {
      return;
    }
    // Reserve the processor before the first asynchronous acquisition to
    // prevent two share signals from writing the same Mark draft concurrently.
    _processingShare = true;
    final revision = _draftRevision;
    final actor = _actor;
    try {
      final coordinator = await _fileCoordinator();
      if (!mounted ||
          coordinator == null ||
          _restoring ||
          revision != _draftRevision ||
          actor != _actor) {
        return;
      }
      SharedPayload? payload;
      while (mounted &&
          revision == _draftRevision &&
          actor == _actor &&
          (payload = ingress.takeShare(profileId: profileId)) != null) {
        final item = payload!;
        if (item.kind == SharedPayloadKind.text) {
          final incoming = item.text?.trim() ?? '';
          if (incoming.isEmpty) continue;
          setState(() {
            _input.text = [
              if (_input.text.trim().isNotEmpty) _input.text.trim(),
              incoming,
            ].join('\n');
            _result = null;
          });
          await _saveDraft();
          if (_input.text.length > 600) {
            _show(
              'Texte conservé. Raccourcissez votre demande avant de continuer.',
            );
          }
          continue;
        }
        if (item.kind == SharedPayloadKind.url) {
          final link = item.url?.toString() ?? '';
          if (!_isSafeLink(link)) {
            _show('Ce lien partagé n’est pas pris en charge.');
            continue;
          }
          if (!_links.contains(link)) {
            setState(() {
              _links = [..._links, link];
              _result = null;
            });
            await _saveDraft();
          }
          continue;
        }
        if (item.files.length > 4) {
          _show('Sélectionnez au maximum quatre fichiers à la fois.');
          continue;
        }
        List<StoredLocalFile> acquired = const [];
        try {
          final captured = await SharedPayloadCoordinator(coordinator.store)
              .capture(
                item,
                owner: _owner,
                purpose: 'mark_intake',
                sensitivity: 'private',
                fileIdFor: (index, source) =>
                    'mark-share-${DateTime.now().microsecondsSinceEpoch}-$index',
              );
          acquired = captured.files;
          final tooLarge = <StoredLocalFile>[];
          for (final file in acquired) {
            if (await File(file.path).length() > 25 * 1024 * 1024) {
              tooLarge.add(file);
            }
          }
          if (tooLarge.isNotEmpty ||
              !mounted ||
              revision != _draftRevision ||
              actor != _actor) {
            throw StateError('Shared file invalid or Mark actor changed');
          }
          setState(() {
            _attachments = [
              ..._attachments,
              for (var index = 0; index < acquired.length; index++)
                {
                  'file_id': acquired[index].fileId,
                  'name': p.basename(item.files[index].name),
                  'purpose': acquired[index].purpose,
                  if ({
                    '.png',
                    '.jpg',
                    '.jpeg',
                  }.contains(p.extension(acquired[index].path).toLowerCase()))
                    'kind': 'photo',
                },
            ];
            _result = null;
          });
          await _saveDraft();
        } on Object {
          for (final file in acquired) {
            try {
              await coordinator.store.remove(file.fileId);
            } on Object {
              // Unreferenced Profile staging remains for routine cleanup.
            }
          }
          if (mounted && revision == _draftRevision) {
            _show(
              'Le fichier partagé n’a pas été conservé. Réessayez depuis le partage.',
            );
          }
        }
      }
    } on Object {
      if (mounted && revision == _draftRevision) {
        _show('Ce contenu partagé n’a pas pu être ajouté.');
      }
    } finally {
      _processingShare = false;
    }
  }

  Future<void> _openVoiceInput() async {
    if (_busy || _restoring || _voiceCapture || _dictating) return;
    final revision = _draftRevision;
    var canDictate = false;
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      try {
        canDictate =
            await const MethodChannel('makolo/native_dictation')
                .invokeMethod<bool>('available') ==
            true;
      } on Object {
        // No installed system recognition service is a valid configuration.
      }
    }
    if (!mounted || revision != _draftRevision) return;
    final choice = await showModalBottomSheet<String>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (canDictate)
              ListTile(
                leading: const Icon(Icons.mic_outlined),
                title: const Text('Dicter une demande'),
                subtitle: const Text(
                  'Reconnaissance du téléphone, selon la langue et le réseau',
                ),
                onTap: () => Navigator.pop(sheetContext, 'dictation'),
              ),
            ListTile(
              leading: const Icon(Icons.graphic_eq),
              title: const Text('Enregistrer un audio'),
              subtitle: const Text(
                'Conserver une pièce locale, sans transcription',
              ),
              onTap: () => Navigator.pop(sheetContext, 'audio'),
            ),
          ],
        ),
      ),
    );
    if (!mounted || revision != _draftRevision) return;
    if (choice == 'dictation') {
      setState(() => _dictating = true);
    } else if (choice == 'audio') {
      await _openVoiceCapture();
    }
  }

  void _acceptDictation(String value) {
    if (!_dictating || !mounted || value.trim().isEmpty) return;
    setState(() {
      _input.text = [
        if (_input.text.trim().isNotEmpty) _input.text.trim(),
        value.trim(),
      ].join('\n');
      _dictating = false;
      _result = null;
      _pendingConfirmationCode = null;
      _pendingConfirmationKey = null;
    });
    unawaited(_saveDraft());
    if (_input.text.length > 600) {
      _show('Texte conservé. Raccourcissez votre demande avant de continuer.');
    }
  }

  Future<void> _openVoiceCapture() async {
    if (_busy || _voiceCapture) return;
    final revision = _draftRevision;
    final actor = _actor;
    final files = await _fileCoordinator();
    if (!mounted || revision != _draftRevision || actor != _actor) return;
    if (files == null) {
      _show('L’enregistrement n’est pas disponible dans cette session.');
      return;
    }
    setState(() {
      _voiceStore = files.store;
      _voiceCapture = true;
    });
  }

  Future<void> _acceptVoiceFile(StoredLocalFile file) async {
    final revision = _draftRevision;
    final actor = _actor;
    if (!mounted ||
        !_voiceCapture ||
        widget.runtime.session?.profileId != file.profileId) {
      // The recorder still owns this staged file and cleans it on disposal.
      throw StateError('Mark actor changed before audio draft adoption');
    }
    setState(() {
      _attachments = [
        ..._attachments,
        {
          'file_id': file.fileId,
          'name': 'Enregistrement audio',
          'purpose': file.purpose,
          'kind': 'audio',
        },
      ];
    });
    await _saveDraft();
    if (!mounted || revision != _draftRevision || actor != _actor) return;
    setState(() {
      _voiceCapture = false;
      _dictating = false;
      _voiceStore = null;
    });
  }

  Future<void> _pickFiles() async {
    final revision = _draftRevision;
    final coordinator = await _fileCoordinator();
    if (revision != _draftRevision || !mounted) return;
    if (coordinator == null) {
      _show(
        'Les pièces jointes locales ne sont pas disponibles dans cette session.',
      );
      return;
    }
    final selectedNames = <String>[];
    final result = await coordinator.pickFiles(
      owner: _owner,
      purpose: 'mark_intake',
      fileIdFor: (index, file) {
        selectedNames.add(file.name);
        return 'mark-${DateTime.now().microsecondsSinceEpoch}-$index';
      },
    );
    if (!mounted || revision != _draftRevision) return;
    if (!result.acquired) {
      _show('Aucune pièce jointe n’a été ajoutée.');
      return;
    }
    setState(() {
      _attachments = [
        ..._attachments,
        ...result.files.asMap().entries.map(
          (entry) => {
            'file_id': entry.value.fileId,
            'name':
                entry.key < selectedNames.length &&
                    selectedNames[entry.key].trim().isNotEmpty
                ? selectedNames[entry.key].trim()
                : 'Document',
            'purpose': entry.value.purpose,
          },
        ),
      ];
    });
    await _saveDraft();
  }

  Future<void> _capturePhoto() => _acquirePhoto(capture: true);

  Future<void> _pickPhoto() => _acquirePhoto(capture: false);

  Future<void> _acquirePhoto({required bool capture}) async {
    final revision = _draftRevision;
    final coordinator = await _fileCoordinator();
    if (revision != _draftRevision || !mounted) return;
    if (coordinator == null) {
      _show('Les images ne sont pas disponibles dans cette session.');
      return;
    }
    final fileId = 'mark-photo-${DateTime.now().microsecondsSinceEpoch}';
    final result = capture
        ? await coordinator.capturePhoto(
            fileId: fileId,
            owner: _owner,
            purpose: 'mark_intake',
          )
        : await coordinator.pickPhoto(
            fileId: fileId,
            owner: _owner,
            purpose: 'mark_intake',
          );
    if (!mounted || revision != _draftRevision) return;
    if (!result.acquired) {
      if (result.status != FileAcquisitionStatus.cancelled) {
        _show('Impossible d’ajouter cette image.');
      }
      return;
    }
    setState(() {
      _attachments = [
        ..._attachments,
        {
          'file_id': result.files.single.fileId,
          'name': capture ? 'Photo' : 'Image',
          'purpose': result.files.single.purpose,
          'kind': 'photo',
        },
      ];
    });
    await _saveDraft();
  }

  Future<void> _previewAttachment(Map<String, dynamic> item) async {
    final id = item['file_id']?.toString();
    if (id == null || id.isEmpty) return;
    final revision = _draftRevision;
    final actor = _actor;
    try {
      final coordinator = await _fileCoordinator();
      if (!mounted || revision != _draftRevision || actor != _actor) return;
      final file = await coordinator?.store.read(id);
      if (!mounted || revision != _draftRevision || actor != _actor) return;
      if (file == null || !await File(file.path).exists()) {
        _show('Cette pièce locale n’est plus disponible.');
        return;
      }
      if (item['kind'] == 'photo') {
        await showDialog<void>(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: const Text('Image enregistrée'),
            content: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 500, maxHeight: 540),
              child: Image.file(
                File(file.path),
                fit: BoxFit.contain,
                errorBuilder: (_, _, _) =>
                    const Text('Impossible de prévisualiser cette image.'),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Fermer'),
              ),
            ],
          ),
        );
      } else if (item['kind'] == 'audio') {
        final player = AudioPlayer();
        try {
          await player.setFilePath(file.path);
          if (!mounted || revision != _draftRevision || actor != _actor) {
            return;
          }
          await showDialog<void>(
            context: context,
            builder: (dialogContext) => AlertDialog(
              title: const Text('Enregistrement audio'),
              content: const Text(
                'Écoutez votre fichier enregistré sur cet appareil.',
              ),
              actions: [
                TextButton(
                  onPressed: () => unawaited(player.play()),
                  child: const Text('Écouter'),
                ),
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext),
                  child: const Text('Fermer'),
                ),
              ],
            ),
          );
        } finally {
          await player.dispose();
        }
      } else {
        if (mounted) {
          _show(
            'Le fichier est conservé, mais son aperçu n’est pas disponible ici.',
          );
        }
      }
    } on Object {
      if (mounted) _show('Impossible d’ouvrir cette pièce locale.');
    }
  }

  Future<void> _saveToPersonalResources(Map<String, dynamic> item) async {
    final actor = _actor;
    final runtime = widget.runtime;
    if (actor is! PersonalActorContext ||
        _busy ||
        _restoring ||
        _voiceCapture ||
        runtime.resources == null ||
        runtime.session?.profileId != runtime.resources?.profileId) {
      return;
    }
    final fileId = item['file_id']?.toString();
    if (fileId == null || fileId.isEmpty) return;
    final revision = _draftRevision;
    try {
      final coordinator = await _fileCoordinator();
      if (!mounted || revision != _draftRevision || actor != _actor) return;
      final file = await coordinator?.store.read(fileId);
      if (file == null ||
          file.owner != 'profile' ||
          file.purpose != 'mark_intake' ||
          !await File(file.path).exists()) {
        _show('Ce document local n’est plus accessible.');
        return;
      }
      const supported = {
        '.pdf',
        '.docx',
        '.doc',
        '.txt',
        '.jpg',
        '.jpeg',
        '.png',
      };
      final extension = p.extension(file.path).toLowerCase();
      if (!supported.contains(extension)) {
        _show('Ce format ne peut pas être conservé comme document.');
        return;
      }
      final candidate = p.basename(item['name']?.toString() ?? '');
      final fileName = p.extension(candidate).toLowerCase() == extension
          ? candidate
          : 'Document$extension';
      final destination = Uri(
        path: '/me/resources/documents/add',
        queryParameters: {'mark_file': fileId, 'mark_name': fileName},
      ).toString();
      final savedId = await context.push<String>(destination);
      if (!mounted ||
          revision != _draftRevision ||
          actor != _actor ||
          !identical(runtime, widget.runtime) ||
          savedId == null ||
          savedId.trim().isEmpty) {
        return;
      }
      setState(() {
        _attachments = [
          for (final attachment in _attachments)
            if (attachment['file_id'] == fileId)
              {...attachment, 'saved_asset_id': savedId}
            else
              attachment,
        ];
        _result = MarkResult(
          state: 'completed',
          message: 'Document confirmé dans Mes ressources.',
          handoff: const {
            'owner': 'personal_assets',
            'surface': 'resource_detail',
          },
          raw: {
            'result': {'kind': 'personal_asset', 'id': savedId},
          },
        );
      });
      await _saveDraft();
    } on Object {
      if (mounted && revision == _draftRevision) {
        _show('La conservation du document n’a pas été confirmée.');
      }
    }
  }

  Future<void> _removeAttachment(Map<String, dynamic> item) async {
    final revision = _draftRevision;
    final actor = _actor;
    final fileId = item['file_id']?.toString();
    setState(() {
      _attachments = [
        for (final entry in _attachments)
          if (entry['file_id'] != fileId) entry,
      ];
    });
    await _saveDraft();
    if (!mounted || revision != _draftRevision || actor != _actor) return;
    if (fileId == null || fileId.isEmpty) return;
    try {
      final coordinator = await _fileCoordinator();
      if (!mounted || revision != _draftRevision || actor != _actor) return;
      final staged = await coordinator?.store.read(fileId);
      if (staged != null &&
          staged.owner == _owner &&
          staged.purpose == 'mark_intake') {
        await coordinator!.store.remove(fileId);
      }
    } on Object {
      if (mounted) _show('La copie locale n’a pas pu être supprimée.');
    }
  }

  Future<void> _removeSelectedContext() async {
    setState(() {
      _selectedContext = null;
      _result = null;
    });
    await _saveDraft();
  }

  Future<void> _chooseOption(Map option) async {
    if (_busy || _restoring) return;
    final selected = markClarificationSelection(option);
    if (selected == null) return;
    setState(() {
      _selectedContext = selected;
      _result = null;
      _pendingConfirmationCode = null;
      _pendingConfirmationKey = null;
    });
    await _saveDraft();
    if (mounted) await _submit();
  }

  String get _owner => switch (_actor) {
    PersonalActorContext() => 'profile',
    SpaceActorContext(:final space) => 'space:${space.slug}',
  };

  Future<void> _saveDraft() => _repository.saveDraft(
    actor: _actor,
    input: _input.text,
    inputKind: _attachments.isEmpty ? 'text' : 'document',
    attachments: _attachments,
    links: _links,
    selected: _selectedContext,
    pendingConfirmationCode: _pendingConfirmationCode,
    pendingConfirmationKey: _pendingConfirmationKey,
  );

  String _newIdempotencyKey() {
    final random = Random.secure();
    return List.generate(
      4,
      (_) => random.nextInt(1 << 32).toRadixString(16).padLeft(8, '0'),
    ).join();
  }

  void _cancelConfirmation() {
    setState(() {
      _result = null;
      _pendingConfirmationCode = null;
      _pendingConfirmationKey = null;
    });
    unawaited(_saveDraft());
  }

  Future<void> _confirmAction() async {
    final proposal = _result;
    if (_busy || proposal?.state != 'needs_confirmation') return;
    final action = proposal?.action;
    if (action?['code'] != 'redeem_recognition' ||
        _actor is! PersonalActorContext) {
      return;
    }
    final target = action?['target'];
    if (target is! Map ||
        target['kind'] != 'recognition_reward' ||
        target['id'] is! String) {
      _show('Cette confirmation ne peut pas être exécutée ici.');
      return;
    }
    final id = target['id'] as String;
    final operationKey = _pendingConfirmationKey ?? _newIdempotencyKey();
    final revision = _draftRevision;
    final actor = _actor;
    final repository = _repository;
    setState(() {
      _busy = true;
      _pendingConfirmationCode = 'redeem_recognition';
      _pendingConfirmationKey = operationKey;
    });
    final result = await repository.submit(
      actor: actor,
      input: _input.text.trim(),
      selected: {'kind': 'recognition_reward', 'id': id},
      attachments: _attachments,
      links: _links,
      allowTextOnly: _attachments.isNotEmpty || _links.isNotEmpty,
      confirmation: {'code': 'redeem_recognition', 'target_id': id},
      idempotencyKey: operationKey,
    );
    if (!mounted ||
        revision != _draftRevision ||
        repository != _repository ||
        actor != _actor) {
      return;
    }
    setState(() {
      _busy = false;
      _result = result;
      if (result.state == 'completed') {
        _pendingConfirmationCode = null;
        _pendingConfirmationKey = null;
      }
    });
    if (result.state == 'completed' &&
        (_attachments.isNotEmpty || _links.isNotEmpty)) {
      await _saveDraft();
    }
  }

  Future<void> _submit() async {
    if (_busy || _restoring || _voiceCapture || _dictating) return;
    final input = _input.text.trim();
    if (input.length > 600) {
      _show('Raccourcissez votre demande à 600 caractères avant de continuer.');
      return;
    }
    if (input.isEmpty && _attachments.isEmpty && _links.isEmpty) {
      _show('Écrivez une demande ou ajoutez une pièce.');
      return;
    }
    final revision = _draftRevision;
    final actor = _actor;
    final repository = _repository;
    final attachments = List<Map<String, dynamic>>.of(_attachments);
    final links = List<String>.of(_links);
    var allowTextOnly = false;
    if ((attachments.isNotEmpty || links.isNotEmpty) && input.isNotEmpty) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Continuer avec le texte seulement ?'),
          content: const Text(
            'Les pièces et liens restent dans le brouillon local. '
            'Ils ne seront ni envoyés ni analysés par Makolo.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Garder mon brouillon'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Continuer avec le texte'),
            ),
          ],
        ),
      );
      if (!mounted || revision != _draftRevision || actor != _actor) return;
      if (confirmed != true) return;
      allowTextOnly = true;
    }
    setState(() => _busy = true);
    final result = await repository.submit(
      actor: actor,
      input: input,
      inputKind: 'text',
      attachments: attachments,
      links: links,
      selected: _selectedContext,
      allowTextOnly: allowTextOnly,
    );
    if (!mounted ||
        revision != _draftRevision ||
        repository != _repository ||
        actor != _actor) {
      return;
    }
    setState(() {
      _busy = false;
      _result = result;
      if (result.state == 'needs_confirmation' &&
          result.action?['code'] == 'redeem_recognition') {
        if (_pendingConfirmationCode != 'redeem_recognition') {
          _pendingConfirmationKey = null;
        }
        _pendingConfirmationCode = 'redeem_recognition';
        _pendingConfirmationKey ??= _newIdempotencyKey();
      } else if (result.state != 'confirmation_unknown') {
        _pendingConfirmationCode = null;
        _pendingConfirmationKey = null;
      }
    });
    if (_pendingConfirmationCode != null) await _saveDraft();
  }

  void _show(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  void _openAvatar() {
    showMakoloAvatarSheet(
      context,
      runtime: widget.runtime,
      onConnections: () => context.push(connectionsRouteForActor(_actor)),
      onEditProfile: () => context.push('/me/profile'),
      onBilling: () => context.push(subscriptionRouteForActor(_actor)),
      onSettings: () => context.push('/settings'),
      onSwitchAccount:
          widget.onSwitchAccount ??
          () {
            widget.runtime.recovery.markAccountSwitch();
            context.push('/accounts');
          },
      onLogout: widget.onLogout,
    );
  }

  @override
  Widget build(BuildContext context) {
    final actor = _actor;
    return Scaffold(
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(64),
        child: StreamBuilder<StoredProjection?>(
          stream: _meStream,
          builder: (context, snapshot) {
            final identity = snapshot.data?.payload['identity'];
            final name = identity is Map ? identity['display_name'] : null;
            final avatarUrl = identity is Map ? identity['avatar_url'] : null;
            final baseUri = widget.runtime.api?.baseUri;
            final resolved =
                avatarUrl is String && avatarUrl.isNotEmpty && baseUri != null
                ? baseUri.resolve(avatarUrl)
                : null;
            final safeAvatar =
                resolved != null &&
                (resolved.scheme == 'https' || resolved.scheme == 'http') &&
                resolved.host == baseUri!.host;
            return MakoloPrimaryHeader(
              kind: MakoloHeaderKind.mark,
              avatarLetter: name is String && name.trim().isNotEmpty
                  ? name.trim().substring(0, 1).toUpperCase()
                  : null,
              avatarProfileId: widget.runtime.personal?.store.profileId,
              avatarUrl: safeAvatar ? resolved.toString() : null,
              avatarApi: widget.runtime.api,
              avatarRevision: snapshot.data?.receivedAt,
              onAvatar: _openAvatar,
            );
          },
        ),
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
                      focusNode: _inputFocus,
                      readOnly: _busy || _restoring,
                      minLines: 4,
                      maxLines: 9,
                      maxLength: 600,
                      textInputAction: TextInputAction.newline,
                      decoration: const InputDecoration(
                        hintText: 'Ex. Retrouve mon billet pour ce soir',
                        alignLabelWithHint: true,
                      ),
                      onChanged: (_) {
                        setState(() {
                          _result = null;
                          _pendingConfirmationCode = null;
                          _pendingConfirmationKey = null;
                        });
                        unawaited(_saveDraft());
                      },
                    ),
                    if (_selectedContext != null ||
                        _attachments.isNotEmpty ||
                        _links.isNotEmpty) ...[
                      if (_selectedContext != null)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  'Élément sélectionné pour cette demande',
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              ),
                              MakoloIconActionButton(
                                icon: Icons.close,
                                tooltip: 'Retirer le contexte sélectionné',
                                onPressed: _busy
                                    ? null
                                    : () => unawaited(_removeSelectedContext()),
                              ),
                            ],
                          ),
                        ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final link in _links)
                            Chip(
                              avatar: const Icon(Icons.link, size: 18),
                              label: ConstrainedBox(
                                constraints: const BoxConstraints(
                                  maxWidth: 280,
                                ),
                                child: Text(
                                  link,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              onDeleted: _busy
                                  ? null
                                  : () => unawaited(_removeLink(link)),
                              deleteButtonTooltipMessage: 'Retirer ce lien',
                            ),
                          for (final item in _attachments) ...[
                            InputChip(
                              avatar: Icon(
                                item['kind'] == 'audio'
                                    ? Icons.mic_none
                                    : item['kind'] == 'photo'
                                    ? Icons.image_outlined
                                    : Icons.attach_file,
                                size: 18,
                              ),
                              label: Text(
                                '${item['name']?.toString() ?? 'Pièce'}'
                                '${item['saved_asset_id'] != null ? ' ✓' : ''}',
                              ),
                              onPressed: _busy
                                  ? null
                                  : () => unawaited(_previewAttachment(item)),
                              onDeleted: _busy
                                  ? null
                                  : () => unawaited(_removeAttachment(item)),
                              deleteButtonTooltipMessage: 'Retirer cette pièce',
                            ),
                            if (actor is PersonalActorContext &&
                                widget.runtime.resources != null &&
                                item['kind'] != 'audio' &&
                                item['saved_asset_id'] == null)
                              MakoloIconActionButton(
                                icon: Icons.drive_file_move_outline,
                                tooltip: 'Conserver dans Mes documents',
                                onPressed: _busy || _restoring
                                    ? null
                                    : () => unawaited(
                                        _saveToPersonalResources(item),
                                      ),
                              ),
                          ],
                        ],
                      ),
                      if (_attachments.isNotEmpty || _links.isNotEmpty)
                        const Padding(
                          padding: EdgeInsets.only(top: 8),
                          child: Text(
                            'Pièces et liens conservés dans le brouillon local. '
                            'Ils ne sont pas transmis avec la demande.',
                          ),
                        ),
                    ],
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        MakoloActionButton(
                          label: 'Joindre',
                          onPressed: _busy ? null : _pickFiles,
                          appearance: MakoloActionAppearance.secondary,
                          icon: Icons.attach_file,
                        ),
                        MakoloActionButton(
                          label: 'Photo',
                          onPressed: _busy ? null : _capturePhoto,
                          appearance: MakoloActionAppearance.secondary,
                          icon: Icons.photo_camera_outlined,
                        ),
                        MakoloActionButton(
                          label: 'Image',
                          onPressed: _busy ? null : _pickPhoto,
                          appearance: MakoloActionAppearance.secondary,
                          icon: Icons.photo_library_outlined,
                        ),
                        MakoloActionButton(
                          label: 'Voix',
                          onPressed: _busy ? null : _openVoiceInput,
                          appearance: MakoloActionAppearance.secondary,
                          icon: Icons.mic_none,
                        ),
                        MakoloActionButton(
                          label: 'Lien',
                          onPressed: _busy ? null : _addLink,
                          appearance: MakoloActionAppearance.secondary,
                          icon: Icons.link,
                        ),
                      ],
                    ),
                    if (_dictating) ...[
                      const SizedBox(height: 12),
                      MarkDictationCapture(
                        key: ValueKey(
                          'dictation:${widget.runtime.session?.profileId}:$_owner',
                        ),
                        onText: _acceptDictation,
                        onClose: () {
                          if (mounted) setState(() => _dictating = false);
                        },
                      ),
                    ],
                    if (_voiceCapture && _voiceStore != null) ...[
                      const SizedBox(height: 12),
                      MarkVoiceCapture(
                        key: ValueKey(
                          'voice:${widget.runtime.session?.profileId}:$_owner',
                        ),
                        store: _voiceStore!,
                        owner: _owner,
                        onCaptured: _acceptVoiceFile,
                        onClose: () {
                          if (mounted) {
                            setState(() {
                              _voiceCapture = false;
                              _voiceStore = null;
                            });
                          }
                        },
                      ),
                    ],
                    const SizedBox(height: 20),
                    MakoloActionButton(
                      appearance: MakoloActionAppearance.primary,
                      onPressed:
                          _busy || _restoring || _voiceCapture || _dictating
                          ? null
                          : _submit,
                      busy: _busy,
                      label: _busy ? 'Envoi…' : 'Continuer',
                    ),
                    if (_restoring)
                      const Padding(
                        padding: EdgeInsets.only(top: 12),
                        child: Text('Restauration du brouillon…'),
                      ),
                    if (_result != null) ...[
                      const SizedBox(height: 24),
                      _MarkResultView(
                        result: _result!,
                        onChooseOption: (option) =>
                            unawaited(_chooseOption(option)),
                        onEdit: () => _inputFocus.requestFocus(),
                        onCancel: _result!.state == 'needs_confirmation'
                            ? _cancelConfirmation
                            : null,
                        onConfirm:
                            _result!.state == 'needs_confirmation' &&
                                _result!.action?['code'] ==
                                    'redeem_recognition' &&
                                actor is PersonalActorContext
                            ? () => unawaited(_confirmAction())
                            : null,
                        onOpenHandoff: switch (markHandoffRoute(
                          _result!,
                          actor,
                        )) {
                          final String path => () => context.push(path),
                          null => null,
                        },
                      ),
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
  const _MarkResultView({
    required this.result,
    required this.onChooseOption,
    required this.onEdit,
    this.onOpenHandoff,
    this.onConfirm,
    this.onCancel,
  });

  final MarkResult result;
  final ValueChanged<Map> onChooseOption;
  final VoidCallback onEdit;
  final VoidCallback? onOpenHandoff;
  final VoidCallback? onConfirm;
  final VoidCallback? onCancel;

  @override
  Widget build(BuildContext context) {
    final question = result.question;
    final action = result.action;
    final handoff = result.handoff;
    final label = switch (result.state) {
      'needs_clarification' => 'Précision nécessaire',
      'needs_confirmation' => 'Confirmation nécessaire',
      'offline_draft' => 'Brouillon local',
      'local_attachments_only' => 'Pièces conservées localement',
      'local_references_only' => 'Liens conservés localement',
      'confirmation_unknown' => 'Résultat à vérifier',
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
                      child: markClarificationSelection(option) == null
                          ? Text(option['label']?.toString() ?? '')
                          : MakoloActionButton(
                              label:
                                  option['label']?.toString() ??
                                  'Choisir cet élément',
                              onPressed: () => onChooseOption(option),
                              appearance: MakoloActionAppearance.secondary,
                            ),
                    ),
              if (result.needsInput)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: MakoloActionButton(
                    label: 'Préciser ma demande',
                    onPressed: onEdit,
                    appearance: MakoloActionAppearance.quiet,
                    icon: Icons.edit_outlined,
                  ),
                ),
              if (action?['consequence'] != null) ...[
                const SizedBox(height: 12),
                Text(action!['consequence'].toString()),
              ],
              if (onConfirm != null) ...[
                const SizedBox(height: 12),
                MakoloActionButton(
                  label: 'Confirmer cette utilisation',
                  onPressed: onConfirm,
                  appearance: MakoloActionAppearance.primary,
                  icon: Icons.check_circle_outline,
                ),
              ],
              if (onCancel != null) ...[
                const SizedBox(height: 8),
                MakoloActionButton(
                  label: 'Annuler cette proposition',
                  onPressed: onCancel,
                  appearance: MakoloActionAppearance.quiet,
                ),
              ],
              if (onOpenHandoff != null) ...[
                const SizedBox(height: 12),
                MakoloActionButton(
                  label: 'Ouvrir la suite',
                  onPressed: onOpenHandoff,
                  appearance: MakoloActionAppearance.primary,
                  icon: Icons.arrow_forward_rounded,
                ),
              ] else if (handoff?['surface'] != null &&
                  result.state == 'resolved') ...[
                const SizedBox(height: 12),
                const Text(
                  'Cette destination n’est pas accessible ici pour le moment.',
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
