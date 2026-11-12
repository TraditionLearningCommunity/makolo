import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
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
  String? _pendingConfirmationCode;
  String? _pendingConfirmationKey;
  Stream<StoredProjection?>? _meStream;

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
  void didUpdateWidget(covariant MarkScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.runtime, widget.runtime)) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      widget.runtime.actorContext?.addListener(_onActorChanged);
      _draftRevision++;
      _repository = MarkRepository(widget.runtime);
      _files = null;
      _voiceStore = null;
      _voiceCapture = false;
      _pendingConfirmationCode = null;
      _pendingConfirmationKey = null;
      _actor =
          widget.runtime.actorContext?.value ?? const PersonalActorContext();
      _result = null;
      _attachments = const [];
      _links = const [];
      _voiceCapture = false;
      _voiceStore = null;
      _pendingConfirmationCode = null;
      _pendingConfirmationKey = null;
      _selectedContext = widget.selectedContext;
      _restoring = true;
      _busy = false;
      _input.clear();
      _meStream = widget.runtime.personal?.watchMe();
      unawaited(_restoreDraft());
    } else if (oldWidget.runtime.personal != widget.runtime.personal) {
      _meStream = widget.runtime.personal?.watchMe();
    }
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_onActorChanged);
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
    final result = await coordinator.pickFiles(
      owner: _owner,
      purpose: 'mark_intake',
      fileIdFor: (index, file) =>
          'mark-${DateTime.now().microsecondsSinceEpoch}-$index',
    );
    if (!mounted || revision != _draftRevision) return;
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
          'name': result.files.single.path.split('/').last,
          'purpose': result.files.single.purpose,
          'kind': 'photo',
        },
      ];
    });
    await _saveDraft();
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
  }

  Future<void> _submit() async {
    if (_busy || _restoring) return;
    final input = _input.text.trim();
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
                      minLines: 7,
                      maxLines: 12,
                      maxLength: 600,
                      textInputAction: TextInputAction.newline,
                      decoration: const InputDecoration(
                        hintText: 'Ex. Retrouve mon billet pour ce soir',
                        alignLabelWithHint: true,
                      ),
                      onChanged: (_) {
                        _result = null;
                        _pendingConfirmationCode = null;
                        _pendingConfirmationKey = null;
                        unawaited(_saveDraft());
                      },
                    ),
                    if (_selectedContext != null ||
                        _attachments.isNotEmpty ||
                        _links.isNotEmpty) ...[
                      if (_selectedContext != null)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Text(
                            'Élément sélectionné pour cette demande',
                            style: Theme.of(context).textTheme.bodySmall,
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
                          for (final item in _attachments)
                            Chip(
                              avatar: const Icon(Icons.attach_file, size: 18),
                              label: Text(item['name']?.toString() ?? 'Pièce'),
                              onDeleted: _busy
                                  ? null
                                  : () => unawaited(_removeAttachment(item)),
                              deleteButtonTooltipMessage: 'Retirer cette pièce',
                            ),
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
                          onPressed: _busy ? null : _openVoiceCapture,
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
                      onPressed: _busy || _restoring || _voiceCapture
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
  });

  final MarkResult result;
  final ValueChanged<Map> onChooseOption;
  final VoidCallback onEdit;
  final VoidCallback? onOpenHandoff;
  final VoidCallback? onConfirm;

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
