import 'dart:io';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../network/api_error.dart';
import '../../network/makolo_api_client.dart';
import '../../platform/files/passport_pdf_saver.dart';
import '../../platform/sharing/share_gateway.dart';
import '../../sync/projection_contract.dart';

/// The Space's canonical Passport, not a second collective identity.
class SpacePassportScreen extends StatefulWidget {
  const SpacePassportScreen({
    super.key,
    required this.runtime,
    required this.slug,
  });
  final AppRuntime runtime;
  final String slug;

  @override
  State<SpacePassportScreen> createState() => _SpacePassportScreenState();
}

class _SpacePassportScreenState extends State<SpacePassportScreen> {
  static const variants = {
    'complete': 'Complet',
    'public': 'Public',
    'thematic': 'Thématique',
    'custom': 'Personnalisé',
  };
  Map<String, dynamic>? source;
  String variant = 'complete';
  String? topic;
  final excluded = <String>{};
  final excludedActivities = <String>{};
  bool loading = true, busy = false;
  String? error;
  int epoch = 0;

  String get root =>
      'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/passport/';

  bool get authorized {
    final value = widget.runtime.actorContext?.value;
    return value is SpaceActorContext && value.space.slug == widget.slug;
  }

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(actorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => reload());
  }

  @override
  void didUpdateWidget(covariant SpacePassportScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime != widget.runtime || oldWidget.slug != widget.slug) {
      oldWidget.runtime.actorContext?.removeListener(actorChanged);
      widget.runtime.actorContext?.addListener(actorChanged);
      ++epoch;
      source = null;
      error = null;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) reload();
      });
    }
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(actorChanged);
    super.dispose();
  }

  void actorChanged() {
    if (!mounted) return;
    ++epoch;
    setState(() {
      source = null;
      error = null;
      loading = true;
    });
    if (authorized) {
      reload();
    } else {
      // The currently open dated/history/share sheet must not remain
      // visible when the active owner is no longer this Space.
      setState(() {
        error =
            'Impossible de consulter le Passeport de cet Espace actuellement.';
        loading = false;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && !authorized && Navigator.of(context).canPop()) {
          Navigator.of(context).pop();
        }
      });
    }
  }

  static Map<String, dynamic> map(Object? value) => value is Map
      ? value.map((key, item) => MapEntry(key.toString(), item))
      : <String, dynamic>{};

  static List<Map<String, dynamic>> rows(Object? value) => value is List
      ? value.whereType<Map>().map(map).toList()
      : <Map<String, dynamic>>[];

  static String? value(Object? item) =>
      item is String && item.trim().isNotEmpty ? item.trim() : null;

  static String datedAt(Object? raw) {
    final parsed = DateTime.tryParse(raw?.toString() ?? '');
    if (parsed == null) return raw?.toString() ?? '';
    final date = parsed.toLocal();
    String two(int item) => item.toString().padLeft(2, '0');
    return '${two(date.day)}/${two(date.month)}/${date.year} ${two(date.hour)}:${two(date.minute)}';
  }

  void message(String text) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
    }
  }

  Future<void> reload() async {
    final api = widget.runtime.api;
    if (!authorized || api == null) {
      if (mounted) {
        setState(() {
          source = null;
          loading = false;
          error = 'Impossible de consulter le Passeport de cet Espace actuellement.';
        });
      }
      return;
    }
    final ticket = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final reply = await api.get(root);
      final data = ProjectionEnvelope.parse(
        reply.jsonObject(),
        expectedProjection: 'space.passport',
      ).data;
      if (!mounted ||
          !authorized ||
          ticket != epoch ||
          data['slug'] != widget.slug) {
        return;
      }
      setState(() {
        source = data;
        loading = false;
        final topics = rows(data['topic_options'])
            .map((item) => value(item['code']))
            .whereType<String>()
            .toSet();
        if (!topics.contains(topic)) topic = null;
      });
    } on Object {
      if (!mounted || ticket != epoch) return;
      setState(() {
        source = null;
        loading = false;
        error = 'Passeport indisponible.';
      });
    }
  }

  List<Map<String, dynamic>> visibleActivities(
    Map<String, dynamic> full, {
    bool showExcluded = false,
  }) {
    final list = rows(full['activities']);
    if (variant == 'complete') return list;
    final ids =
        (map(map(full['composition'])['public_ids'])['activities'] as List?)
            ?.map((id) => id.toString())
            .toSet() ??
        <String>{};
    return list.where((row) {
      final id = row['id']?.toString() ?? '';
      if (!ids.contains(id) ||
          (!showExcluded &&
              excludedActivities.contains(id) &&
              variant == 'custom')) {
        return false;
      }
      if (variant == 'thematic') {
        if (topic == null) return false;
        final codes = row['topic_codes'];
        if (codes is! List || !codes.contains(topic)) return false;
      }
      return true;
    }).toList();
  }

  Map<String, dynamic> presented(Map<String, dynamic> full) {
    if (variant == 'complete') return full;
    final composition = map(full['composition']);
    final identity = Map<String, dynamic>.from(
      map(composition['public_identity']),
    );
    if (variant == 'custom') {
      for (final key in ['bio', 'location', 'links']) {
        if (excluded.contains(key)) {
          identity[key] = key == 'links' ? <Object>[] : '';
        }
      }
    }
    return {
      ...full,
      'variant': variant,
      'identity': identity,
      'activities': visibleActivities(full),
      'established': {
        'trust_verifications': excluded.contains('trust') && variant == 'custom'
            ? []
            : rows(composition['public_trust']),
      },
      'issued': {
        'credential_summary':
            excluded.contains('credentials') && variant == 'custom'
            ? []
            : rows(composition['public_credentials']),
      },
      'collectives': <String, dynamic>{},
    };
  }

  String url(String suffix, {String? selectedVariant}) {
    final current = selectedVariant ?? variant;
    final parameters = <String, dynamic>{'variant': current};
    if (current == 'thematic' && topic != null) parameters['topic'] = topic;
    if (current == 'custom') {
      if (excluded.isNotEmpty) {
        parameters['exclude'] = excluded.toList()..sort();
      }
      if (excludedActivities.isNotEmpty) {
        parameters['exclude_activity'] = excludedActivities.toList()..sort();
      }
    }
    return Uri(path: root + suffix, queryParameters: parameters).toString();
  }

  Future<void> guarded(Future<void> Function() body) async {
    if (busy || !authorized || widget.runtime.api == null) return;
    setState(() => busy = true);
    try {
      await body();
    } on MakoloApiError catch (failure) {
      if (failure.statusCode == 401 ||
          failure.statusCode == 403 ||
          failure.statusCode == 404) {
        ++epoch;
        if (mounted) {
          setState(() {
            source = null;
            error = 'Impossible de confirmer vos droits pour cette action.';
          });
        }
      } else {
        message('Action indisponible.');
      }
    } on Object {
      message('Action indisponible.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<String?> issue({bool shareable = false}) async {
    final api = widget.runtime.api;
    if (api == null || !authorized) return null;
    final selected = shareable && variant == 'complete' ? 'public' : variant;
    final response = await api.post(
      url('issue/', selectedVariant: selected),
      body: <String, dynamic>{},
    );
    final data = ProjectionEnvelope.parse(
      response.jsonObject(),
      expectedProjection: 'space.passport.issuance',
    ).data;
    return authorized ? value(data['id']) : null;
  }

  Future<void> withPdf({
    String? datedId,
    required Future<void> Function(String path) action,
  }) async {
    final api = widget.runtime.api;
    final startActor = widget.runtime.actorContext?.value;
    if (api == null || !authorized || startActor is! SpaceActorContext) return;
    final spaceId = startActor.space.id;
    final dir = await Directory.systemTemp.createTemp('makolo-space-passport-');
    final path = '${dir.path}/passeport-makolo.pdf';
    try {
      final route = datedId == null
          ? url('pdf/')
          : '${root}history/$datedId/pdf/';
      final reply = await api.download(route, destinationPath: path);
      final actorNow = widget.runtime.actorContext?.value;
      if (!mounted ||
          !authorized ||
          actorNow is! SpaceActorContext ||
          actorNow.space.id != spaceId) {
        return;
      }
      final disposition =
          reply.headers.entries
              .where((item) => item.key.toLowerCase() == 'content-disposition')
              .map((item) => item.value)
              .firstOrNull ??
          '';
      final filename = RegExp(r'filename="?([A-Za-z0-9._-]+\.pdf)"?')
          .firstMatch(disposition)
          ?.group(1);
      var file = path;
      if (filename != null && filename.startsWith('passeport-makolo-')) {
        file = '${dir.path}/$filename';
        await File(path).rename(file);
      }
      await action(file);
    } finally {
      try {
        await dir.delete(recursive: true);
      } on Object {
        /* temporary */
      }
    }
  }

  Future<void> pdf({String? datedId}) => guarded(() async {
    await withPdf(
      datedId: datedId,
      action: (path) async {
        await savePassportPdf(path, path.split(Platform.pathSeparator).last);
        message('PDF enregistré.');
      },
    );
  });

  Future<void> sharePdf() => guarded(() async {
    await withPdf(
      action: (path) => const SystemShareGateway().shareFiles(paths: [path]),
    );
  });

  Future<String?> shareLink(String id) async {
    final response = await widget.runtime.api!.post(
      '${root}history/$id/share/',
      body: {'days': 7},
    );
    final data = ProjectionEnvelope.parse(
      response.jsonObject(),
      expectedProjection: 'space.passport.share',
    ).data;
    return value(data['share_url']);
  }

  Future<void> copyIssuedLink() => guarded(() async {
    final id = await issue(shareable: true);
    if (id == null) return;
    final link = await shareLink(id);
    if (link == null) return;
    await Clipboard.setData(ClipboardData(text: link));
    message('Lien copié.');
  });

  Future<void> sharePublicLink() => guarded(() async {
    if (source?['public_profile_enabled'] != true) {
      message('Passeport public indisponible.');
      return;
    }
    final api = widget.runtime.api!;
    final path = value(source?['public_path']);
    if (path == null || !path.startsWith('/') || path.startsWith('//')) return;
    final link = api.baseUri.resolve(path).toString();
    await Clipboard.setData(ClipboardData(text: link));
    await const SystemShareGateway().shareText(link);
  });

  Future<void> shareInMakolo() => guarded(() async {
    final recipient = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (dialog) => _RecipientPicker(
        api: widget.runtime.api!,
        onSelected: (person) => Navigator.pop(dialog, person),
      ),
    );
    if (recipient == null || !authorized) return;
    final recipientId = value(recipient['id']);
    if (recipientId == null) return;
    final id = await issue(shareable: true);
    if (id == null) return;
    await widget.runtime.api!.post(
      '${root}history/$id/deliver/',
      body: {'recipient_id': recipientId},
    );
    message('Passeport partagé dans Makolo.');
  });

  Future<void> share() async {
    if (busy || source == null) return;
    final action = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (dialog) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final item in <(String, String, IconData)>[
              ('pdf', 'Partager le PDF', Icons.picture_as_pdf_outlined),
              ('makolo', 'Partager dans Makolo', Icons.people_outline),
              ('public', 'Partager le lien public', Icons.link_outlined),
              ('dated', 'Copier le lien du Passeport', Icons.copy_outlined),
            ])
              ListTile(
                leading: Icon(item.$3),
                title: Text(item.$2),
                enabled:
                    item.$1 != 'public' ||
                    source?['public_profile_enabled'] == true,
                onTap: () => Navigator.pop(dialog, item.$1),
              ),
          ],
        ),
      ),
    );
    switch (action) {
      case 'pdf':
        await sharePdf();
      case 'makolo':
        await shareInMakolo();
      case 'public':
        await sharePublicLink();
      case 'dated':
        await copyIssuedLink();
    }
  }

  Future<void> shareVersion(String id) => guarded(() async {
    final link = await shareLink(id);
    if (link == null) return;
    await Clipboard.setData(ClipboardData(text: link));
    await const SystemShareGateway().shareText(link);
  });

  Future<void> revokeVersion(String id) => guarded(() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: const Text('Révoquer cette version ?'),
        actions: [
          MakoloActionButton(
            label: 'Annuler',
            appearance: MakoloActionAppearance.quiet,
            onPressed: () => Navigator.pop(dialog, false),
          ),
          MakoloActionButton(
            label: 'Révoquer',
            appearance: MakoloActionAppearance.danger,
            onPressed: () => Navigator.pop(dialog, true),
          ),
        ],
      ),
    );
    if (yes != true || !authorized) return;
    await widget.runtime.api!.post(
      '${root}history/$id/revoke/',
      body: <String, dynamic>{},
    );
    message('Version révoquée.');
  });

  Future<void> history() async {
    if (busy || !authorized) return;
    try {
      final response = await widget.runtime.api!.get('${root}history/');
      final data = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'space.passport.history',
      ).data;
      if (!mounted || !authorized) return;
      final items = rows(data['items']);
      var hasMore = data['has_more'] == true;
      var nextOffset = data['next_offset'] is int
          ? data['next_offset'] as int
          : items.length;
      var pageLoading = false;
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (sheet) => StatefulBuilder(
          builder: (sheet, update) => SafeArea(
            child: SizedBox(
              height: MediaQuery.sizeOf(sheet).height * 0.65,
              child: Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text(
                      'Versions datées',
                      style: Theme.of(sheet).textTheme.titleLarge,
                    ),
                  ),
                  Expanded(
                    child: ListView(
                      children: [
                        for (final item in items)
                          if (value(item['id']) case final id?)
                            ListTile(
                              leading: const Icon(Icons.history_outlined),
                              title: Text(
                                value(item['document_id']) ?? 'Passeport',
                              ),
                              subtitle: Text(
                                '${datedAt(item['generated_at'])} · ${variants[item['variant']] ?? ''}${item['revoked'] == true ? ' · Révoquée' : ''}${item['integrity_ok'] != true ? ' · Non intègre' : ''}',
                              ),
                              onTap: item['integrity_ok'] == true
                                  ? () {
                                      Navigator.pop(sheet);
                                      final route = value(
                                        item['verification_path'],
                                      );
                                      if (route != null && mounted) {
                                        context.push(route);
                                      }
                                    }
                                  : null,
                              trailing: Wrap(
                                spacing: 0,
                                children: [
                                  MakoloIconActionButton(
                                    tooltip: 'Télécharger cette version',
                                    icon: Icons.picture_as_pdf_outlined,
                                    onPressed: item['integrity_ok'] == true
                                        ? () {
                                            Navigator.pop(sheet);
                                            pdf(datedId: id);
                                          }
                                        : null,
                                  ),
                                  MakoloIconActionButton(
                                    tooltip: 'Partager cette version',
                                    icon: Icons.share_outlined,
                                    onPressed:
                                        item['integrity_ok'] != true ||
                                            item['revoked'] == true ||
                                            item['variant'] == 'complete'
                                        ? null
                                        : () {
                                            Navigator.pop(sheet);
                                            shareVersion(id);
                                          },
                                  ),
                                  MakoloIconActionButton(
                                    tooltip: 'Révoquer cette version',
                                    icon: Icons.block_outlined,
                                    onPressed: item['revoked'] == true
                                        ? null
                                        : () {
                                            Navigator.pop(sheet);
                                            revokeVersion(id);
                                          },
                                  ),
                                ],
                              ),
                            ),
                        if (hasMore)
                          ListTile(
                            title: Text(
                              pageLoading
                                  ? 'Chargement…'
                                  : 'Voir plus de versions',
                            ),
                            onTap: pageLoading
                                ? null
                                : () async {
                                    update(() => pageLoading = true);
                                    try {
                                      final next = await widget.runtime.api!.get(
                                        '${root}history/?offset=$nextOffset',
                                      );
                                      final page = ProjectionEnvelope.parse(
                                        next.jsonObject(),
                                        expectedProjection:
                                            'space.passport.history',
                                      ).data;
                                      if (!sheet.mounted || !authorized) return;
                                      update(() {
                                        items.addAll(rows(page['items']));
                                        hasMore = page['has_more'] == true;
                                        nextOffset = page['next_offset'] is int
                                            ? page['next_offset'] as int
                                            : items.length;
                                      });
                                    } on Object {
                                      message('Chargement indisponible.');
                                    } finally {
                                      if (sheet.mounted) {
                                        update(() => pageLoading = false);
                                      }
                                    }
                                  },
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    } on Object {
      message('Historique indisponible.');
    }
  }

  Future<void> edit() async {
    await context.push('/space/${widget.slug}/us/settings');
    if (mounted) await reload();
  }

  Future<void> privacy() async {
    await context.push('/space/${widget.slug}/us/passport/privacy');
    if (mounted) await reload();
  }

  Widget section(String title, List<Widget> items) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          ...items,
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final full = source;
    final current = full == null ? <String, dynamic>{} : presented(full);
    final identity = map(current['identity']);
    final activities = rows(current['activities']);
    final selectableActivities = variant == 'custom' && full != null
        ? visibleActivities(full, showExcluded: true)
        : <Map<String, dynamic>>[];
    final topics = rows(full?['topic_options']);
    final trust = rows(map(current['established'])['trust_verifications']);
    final credentials = rows(map(current['issued'])['credential_summary']);
    final name = value(identity['name']) ?? widget.slug;
    final owner = map(identity['owner_details']);
    final missing = <String>[
      if (value(identity['bio']) == null) 'Présentation',
      if (value(identity['location']) == null) 'Localisation',
      if (rows(identity['links']).isEmpty) 'Site web',
      if (value(owner['email']) == null) 'Adresse e-mail',
      if (value(owner['phone']) == null) 'Téléphone',
      if (activities.isEmpty) 'Activités',
      if (trust.isEmpty) 'Confiance',
      if (credentials.isEmpty) 'Attestations délivrées',
    ];
    return Scaffold(
      appBar: AppBar(
        title: const Text('Passeport'),
        actions: [
          MakoloIconActionButton(
            tooltip: 'Confidentialité',
            icon: Icons.shield_outlined,
            onPressed: full == null || busy ? null : privacy,
          ),
          MakoloIconActionButton(
            tooltip: 'Versions datées',
            icon: Icons.history_outlined,
            onPressed: full == null || busy ? null : history,
          ),
          MakoloIconActionButton(
            tooltip: 'PDF',
            icon: Icons.picture_as_pdf_outlined,
            onPressed: full == null || busy ? null : () => pdf(),
          ),
          MakoloIconActionButton(
            tooltip: 'Partager le Passeport',
            icon: Icons.share_outlined,
            onPressed: full == null || busy ? null : share,
          ),
        ],
      ),
      body: loading
          ? const Center(child: CircularProgressIndicator.adaptive())
          : full == null
          ? Center(
              child: MakoloActionButton(
                label: error ?? 'Réessayer',
                appearance: MakoloActionAppearance.quiet,
                onPressed: reload,
              ),
            )
          : ListView(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 50),
              children: [
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      for (final entry in variants.entries)
                        Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: ChoiceChip(
                            selected: variant == entry.key,
                            label: Text(entry.value),
                            onSelected: (_) => setState(() {
                              variant = entry.key;
                              if (entry.key == 'thematic' &&
                                  topic == null &&
                                  topics.isNotEmpty) {
                                topic = value(topics.first['code']);
                              }
                            }),
                          ),
                        ),
                    ],
                  ),
                ),
                if (variant == 'thematic' && topics.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 14),
                    child: DropdownButtonFormField<String>(
                      initialValue: topic,
                      decoration: const InputDecoration(
                        labelText: 'Thème',
                        border: OutlineInputBorder(),
                      ),
                      items: [
                        for (final row in topics)
                          if (value(row['code']) case final code?)
                            DropdownMenuItem(
                              value: code,
                              child: Text(value(row['label']) ?? code),
                            ),
                      ],
                      onChanged: (choice) => setState(() => topic = choice),
                    ),
                  ),
                if (variant == 'custom')
                  section('À présenter', [
                    Wrap(
                      spacing: 8,
                      children: [
                        for (final entry in const {
                          'bio': 'Présentation',
                          'location': 'Localisation',
                          'links': 'Liens',
                          'trust': 'Confiance',
                          'credentials': 'Attestations',
                        }.entries)
                          FilterChip(
                            label: Text(entry.value),
                            selected: !excluded.contains(entry.key),
                            onSelected: (selected) => setState(() {
                              if (selected) {
                                excluded.remove(entry.key);
                              } else {
                                excluded.add(entry.key);
                              }
                            }),
                          ),
                      ],
                    ),
                    if (selectableActivities.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      const Text('Activités'),
                      for (final activity in selectableActivities)
                        if (value(activity['title']) case final title?)
                          CheckboxListTile(
                            dense: true,
                            contentPadding: EdgeInsets.zero,
                            title: Text(title),
                            value: !excludedActivities.contains(
                              activity['id']?.toString() ?? '',
                            ),
                            onChanged: (selected) => setState(() {
                              final id = activity['id']?.toString() ?? '';
                              if (selected == true) {
                                excludedActivities.remove(id);
                              } else {
                                excludedActivities.add(id);
                              }
                            }),
                          ),
                    ],
                  ]),
                const SizedBox(height: 24),
                Container(
                  padding: const EdgeInsets.all(25),
                  decoration: const BoxDecoration(
                    borderRadius: BorderRadius.all(Radius.circular(25)),
                    gradient: LinearGradient(
                      colors: [Color(0xFF5232DB), Color(0xFF2B176E)],
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Align(
                        alignment: Alignment.topRight,
                        child: Text(
                          'MAKOLO',
                          style: TextStyle(
                            color: Colors.white70,
                            letterSpacing: 3,
                          ),
                        ),
                      ),
                      const SizedBox(height: 45),
                      Text(
                        name,
                        style: Theme.of(context).textTheme.headlineMedium
                            ?.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                            ),
                      ),
                      if (value(identity['headline']) case final headline?)
                        Text(
                          headline,
                          style: const TextStyle(color: Colors.white70),
                        ),
                    ],
                  ),
                ),
                if (value(identity['bio']) case final bio?)
                  Padding(
                    padding: const EdgeInsets.only(top: 20),
                    child: Text(
                      bio,
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                  ),
                section('Informations de l’Espace', [
                  if (variant == 'complete')
                    for (final entry in <String, String>{
                      'email': 'Adresse e-mail',
                      'phone': 'Téléphone',
                    }.entries)
                      if (value(map(identity['owner_details'])[entry.key])
                          case final detail?)
                        ListTile(
                          leading: const Icon(Icons.contact_mail_outlined),
                          title: Text(entry.value),
                          subtitle: Text(detail),
                        ),
                  if (value(identity['location']) case final location?)
                    ListTile(
                      leading: const Icon(Icons.place_outlined),
                      title: const Text('Localisation'),
                      subtitle: Text(location),
                    ),
                  for (final link in rows(identity['links']))
                    if (value(link['url']) case final address?)
                      ListTile(
                        leading: const Icon(Icons.link_outlined),
                        title: Text(value(link['label']) ?? 'Site web'),
                        subtitle: Text(address),
                      ),
                ]),
                section('Activités', [
                  for (final activity in activities)
                    if (value(activity['title']) case final title?)
                      ListTile(
                        leading: const Icon(Icons.event_outlined),
                        title: Text(title),
                      ),
                ]),
                section('Confiance', [
                  for (final row in trust)
                    if (value(row['label']) case final label?)
                      ListTile(
                        leading: const Icon(Icons.verified_outlined),
                        title: Text(label),
                      ),
                ]),
                section('Attestations délivrées', [
                  for (final row in credentials)
                    if (value(row['label']) case final label?)
                      ListTile(
                        leading: const Icon(Icons.workspace_premium_outlined),
                        title: Text(label),
                        trailing: Text(row['count']?.toString() ?? ''),
                      ),
                ]),
                if (variant == 'complete')
                  section('Équipes', [
                    for (final team
                        in (map(current['collectives'])['space_teams']
                                as List? ??
                            []))
                      ListTile(
                        leading: const Icon(Icons.group_outlined),
                        title: Text(team.toString()),
                      ),
                  ]),
                if (variant == 'complete' && missing.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 20),
                    child: ExpansionTile(
                      tilePadding: EdgeInsets.zero,
                      title: const Text('À enrichir'),
                      subtitle: Text('${missing.length} rubriques'),
                      children: [
                        for (final label in missing)
                          ListTile(dense: true, title: Text(label)),
                      ],
                    ),
                  ),
                const SizedBox(height: 20),
                MakoloActionButton(
                  label: 'Modifier le Passeport',
                  appearance: MakoloActionAppearance.secondary,
                  onPressed: edit,
                  icon: Icons.edit_outlined,
                ),
              ],
            ),
    );
  }
}

class _RecipientPicker extends StatefulWidget {
  const _RecipientPicker({required this.api, required this.onSelected});
  final MakoloApiClient api;
  final ValueChanged<Map<String, dynamic>> onSelected;

  @override
  State<_RecipientPicker> createState() => _RecipientPickerState();
}

class _RecipientPickerState extends State<_RecipientPicker> {
  final query = TextEditingController();
  bool searching = false;
  List<Map<String, dynamic>> results = [];

  @override
  void dispose() {
    query.dispose();
    super.dispose();
  }

  Future<void> search() async {
    if (query.text.trim().length < 2 || searching) return;
    setState(() => searching = true);
    try {
      final response = await widget.api.get(
        Uri(
          path: 'api/v1/sharing/recipients/',
          queryParameters: {'q': query.text.trim()},
        ).toString(),
      );
      final data = response.jsonObject()['results'];
      if (mounted) {
        setState(() {
          results = data is List
              ? data
                    .whereType<Map>()
                    .map(
                      (row) =>
                          row.map((key, val) => MapEntry(key.toString(), val)),
                    )
                    .toList()
              : [];
        });
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Recherche indisponible.')),
        );
      }
    } finally {
      if (mounted) setState(() => searching = false);
    }
  }

  @override
  Widget build(BuildContext context) => SafeArea(
    child: Padding(
      padding: EdgeInsets.fromLTRB(
        16,
        12,
        16,
        MediaQuery.viewInsetsOf(context).bottom + 16,
      ),
      child: SizedBox(
        height: MediaQuery.sizeOf(context).height * 0.55,
        child: Column(
          children: [
            Text(
              'Partager dans Makolo',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 14),
            TextField(
              controller: query,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => search(),
              decoration: InputDecoration(
                hintText: 'Nom ou identifiant',
                prefixIcon: const Icon(Icons.search_outlined),
                suffixIcon: MakoloIconActionButton(
                  tooltip: 'Rechercher',
                  onPressed: searching ? null : search,
                  icon: Icons.arrow_forward,
                ),
                border: const OutlineInputBorder(),
              ),
            ),
            if (searching) const LinearProgressIndicator(),
            Expanded(
              child: ListView(
                children: [
                  for (final row in results)
                    ListTile(
                      title: Text(row['name']?.toString() ?? ''),
                      subtitle: Text('@${row['username']?.toString() ?? ''}'),
                      onTap: () => widget.onSelected(row),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
