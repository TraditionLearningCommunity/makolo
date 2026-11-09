import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../platform/sharing/share_gateway.dart';
import 'conversation_attachment_viewer.dart';
import 'conversation_list_tile.dart';
import 'conversation_repository.dart';

/// A Conversation is the coordination around an object, not a generic group.
/// This page only consumes server-approved projections and personal actions.
class ConversationDetailsScreen extends StatefulWidget {
  const ConversationDetailsScreen({
    super.key,
    required this.repository,
    required this.conversationId,
    this.onOpenHistory,
    this.onOpenConversation,
    this.onOpenSubject,
    this.shareGateway = const SystemShareGateway(),
  });

  final ConversationRepository repository;
  final String conversationId;
  final VoidCallback? onOpenHistory;
  final VoidCallback? onOpenConversation;
  final ValueChanged<String>? onOpenSubject;
  final ShareGateway shareGateway;

  @override
  State<ConversationDetailsScreen> createState() =>
      _ConversationDetailsScreenState();
}

class _ConversationDetailsScreenState extends State<ConversationDetailsScreen> {
  String? _busy;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
  }

  Future<void> _refresh() async {
    try {
      await widget.repository.refreshDetail(widget.conversationId);
    } on Object {
      // A network incident never hides a known local Conversation.
    }
  }

  Future<void> _toggle(String action, Map<String, dynamic> state) async {
    if (_busy != null) return;
    setState(() {
      _busy = action;
      _error = null;
    });
    try {
      switch (action) {
        case 'mute':
          await widget.repository.updatePersonalState(
            conversationId: widget.conversationId,
            mute: state['muted'] != true,
          );
          break;
        case 'pin':
          await widget.repository.updatePersonalState(
            conversationId: widget.conversationId,
            pinned: state['pinned'] != true,
          );
          break;
        case 'archive':
          await widget.repository.updatePersonalState(
            conversationId: widget.conversationId,
            archived: state['archived'] != true,
          );
          break;
        case 'hide':
          await widget.repository.updatePersonalState(
            conversationId: widget.conversationId,
            hidden: state['hidden'] != true,
          );
          break;
        case 'revisit':
          await widget.repository.updatePersonalState(
            conversationId: widget.conversationId,
            revisit: state['revisit'] != true,
          );
          break;
      }
    } on Object {
      if (mounted) setState(() => _error = 'Modification non confirmée.');
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  Future<void> _share(Map<String, dynamic> data) async {
    final path = data['share_path']?.toString();
    final base = widget.repository.sync?.api.baseUri;
    // The existing login-protected Django detail route, not a permission
    // grant or a new Sharing token. No URL for an unconfigured environment.
    if (base == null || path != '/conversations/${widget.conversationId}/') {
      return;
    }
    final uri = base.resolve(path!);
    if (uri.scheme != 'https' && uri.scheme != 'http') return;
    try {
      await widget.shareGateway.shareText(uri.toString());
    } on Object {
      if (mounted) setState(() => _error = 'Partage indisponible.');
    }
  }

  Future<void> _openAttachment(Map<String, dynamic> attachment, {
    List<Map<String, dynamic>> gallery = const [],
  }) async {
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (_) => FractionallySizedBox(
        heightFactor: .88,
        child: ConversationAttachmentViewer(
          repository: widget.repository,
          attachment: attachment,
          gallery: gallery,
          initialIndex: gallery.indexWhere((item) => item['id'] == attachment['id']),
        ),
      ),
    );
  }

  Widget _subjectImage(BuildContext context, Map<String, dynamic> subject) {
    final kind = subject['kind']?.toString() ?? '';
    final url = subject['image_url']?.toString();
    final uri = widget.repository.publicContextImageUri(url);
    final color = Theme.of(context).colorScheme;
    final fallback = Container(
      height: 112,
      width: 112,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color.primaryContainer,
      ),
      child: Icon(
        ConversationListTile.contextIcon(kind),
        color: color.onPrimaryContainer,
        size: 48,
      ),
    );
    if (uri == null) return fallback;
    return ClipOval(
      child: Image.network(
        uri.toString(),
        width: 112,
        height: 112,
        fit: BoxFit.cover,
        excludeFromSemantics: true,
        errorBuilder: (_, _, _) => fallback,
      ),
    );
  }

  Widget _hero(BuildContext context, Map<String, dynamic> data) {
    final subject = _map(data['subject']);
    final contextData = _map(data['context']);
    final title = data['title']?.toString() ?? 'Conversation';
    final subjectLabel =
        subject['label']?.toString() ?? contextData['label']?.toString() ?? '';
    final purpose = data['purpose']?.toString() ?? '';
    final kind =
        subject['kind']?.toString() ?? contextData['kind']?.toString() ?? '';
    final type = switch (kind) {
      'direct' => 'Profil',
      'space' => 'Espace',
      'group' => 'Groupe',
      'activity' => 'Activité',
      'occurrence' => 'Occurrence',
      'journey' => 'Démarche',
      'project' => 'Projet',
      'dossier' => 'Dossier',
      'action_proposal' => 'Proposition',
      _ => 'Contexte',
    };
    final theme = Theme.of(context);
    final shareEnabled =
        widget.repository.sync?.api.baseUri != null &&
        data['share_path'] == '/conversations/${widget.conversationId}/';
    final subjectRoute = subject['route']?.toString();
    final canOpenSubject =
        subjectRoute != null &&
        subjectRoute.startsWith('/') &&
        widget.onOpenSubject != null;
    return Column(
      children: [
        const SizedBox(height: 16),
        _subjectImage(context, subject),
        const SizedBox(height: 14),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Text(
            subjectLabel.isNotEmpty ? subjectLabel : title,
            maxLines: 3,
            textAlign: TextAlign.center,
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        const SizedBox(height: 5),
        Text(
          type,
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        if (title.isNotEmpty && title != subjectLabel) ...[
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Text(
              title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: theme.textTheme.titleMedium,
            ),
          ),
        ],
        if (purpose.isNotEmpty) ...[
          const SizedBox(height: 10),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Text(
              purpose,
              maxLines: 5,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium,
            ),
          ),
        ],
        const SizedBox(height: 20),
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 8,
          runSpacing: 8,
          children: [
            _heroAction(
              icon: Icons.forum_outlined,
              label: 'Discussion',
              onTap: widget.onOpenConversation == null
                  ? () => Navigator.of(context).pop()
                  : widget.onOpenConversation!,
            ),
            if (widget.onOpenHistory != null) ...[
              _heroAction(
                icon: Icons.manage_search_rounded,
                label: 'Rechercher',
                onTap: widget.onOpenHistory!,
              ),
            ],
            if (canOpenSubject) ...[
              _heroAction(
                icon: Icons.open_in_new_rounded,
                label: 'Voir l’objet',
                onTap: () => widget.onOpenSubject!(subjectRoute),
              ),
            ],
            if (shareEnabled)
              _heroAction(
                icon: Icons.share_outlined,
                label: 'Partager',
                onTap: () => _share(data),
              ),
          ],
        ),
        const SizedBox(height: 12),
      ],
    );
  }

  Widget _heroAction({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    final colors = Theme.of(context).colorScheme;
    return Semantics(
      button: true,
      label: label,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          child: Column(
            children: [
              Container(
                width: 60,
                height: 52,
                decoration: BoxDecoration(
                  color: colors.surfaceContainerHigh,
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Icon(icon, color: colors.primary, size: 24),
              ),
              const SizedBox(height: 5),
              Text(label, style: Theme.of(context).textTheme.labelMedium),
            ],
          ),
        ),
      ),
    );
  }

  Widget _members(BuildContext context, Map<String, dynamic> data) {
    final members = _map(data['members']);
    final scope = members['scope']?.toString() ?? 'restricted';
    final people = _maps(members['people']);
    if (scope == 'restricted') {
      return _empty(
        context,
        Icons.people_outline_rounded,
        'Les personnes concernées dépendent du contexte de cette conversation. '
        'Leur liste n’est pas affichée ici.',
      );
    }
    if (people.isEmpty) {
      return _empty(
        context,
        Icons.people_outline_rounded,
        'Aucune participation explicite à afficher.',
      );
    }
    return ListView(
      key: const Key('conversation-details-members-list'),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 36),
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(8, 0, 8, 14),
          child: Text(
            scope == 'group' && members['total_count'] is num
                ? '${members['total_count']} membres du Groupe'
                : 'Personnes visibles',
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        if (scope == 'group' &&
            members['total_count'] is num &&
            (members['total_count'] as num).toInt() > people.length)
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 0, 8, 10),
            child: Text(
              'Aperçu des premières personnes. Voir le Groupe pour la liste complète.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        for (final member in people)
          ListTile(
            leading: CircleAvatar(
              backgroundColor: Theme.of(context).colorScheme.primaryContainer,
              child: const Icon(Icons.person_outline_rounded),
            ),
            title: Text(member['label']?.toString() ?? 'Personne'),
            subtitle: member['is_me'] == true ? const Text('Vous') : null,
          ),
      ],
    );
  }

  Widget _media(BuildContext context, Map<String, dynamic> data) {
    final media = _maps(data['media']);
    if (media.isEmpty) {
      return _empty(
        context,
        Icons.perm_media_outlined,
        'Aucun média accessible dans cette conversation.',
      );
    }
    final colors = Theme.of(context).colorScheme;
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth > 580 ? 4 : 3;
        return GridView.builder(
          key: const Key('conversation-details-media-list'),
          padding: const EdgeInsets.fromLTRB(14, 16, 14, 36),
          itemCount: media.length,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            mainAxisSpacing: 10,
            crossAxisSpacing: 10,
            childAspectRatio: .8,
          ),
          itemBuilder: (context, index) {
            final attachment = media[index];
            final name = attachment['name']?.toString() ?? 'Pièce jointe';
            return Semantics(
              button: true,
              label: 'Ouvrir $name',
              child: Material(
                color: colors.surfaceContainerLow,
                borderRadius: BorderRadius.circular(16),
                clipBehavior: Clip.antiAlias,
                child: InkWell(
                  onTap: () => _openAttachment(attachment, gallery: media),
                  child: Column(
                    children: [
                      Expanded(
                        child: Padding(
                          padding: const EdgeInsets.all(6),
                          child: attachment['kind'] == 'image'
                              ? IgnorePointer(
                                  child: ConversationAttachmentViewer(
                                    key: ValueKey(
                                      'conversation-details-media-preview-${attachment['id']?.toString() ?? index.toString()}',
                                    ),
                                    repository: widget.repository,
                                    attachment: attachment,
                                    inline: true,
                                  ),
                                )
                              : Icon(
                                  attachment['kind'] == 'video'
                                      ? Icons.ondemand_video_outlined
                                      : attachment['kind'] == 'audio' ||
                                              attachment['kind'] == 'voice'
                                          ? Icons.graphic_eq_outlined
                                          : attachment['mime_type'] == 'application/pdf'
                                              ? Icons.picture_as_pdf_outlined
                                              : Icons.description_outlined,
                                  color: colors.primary,
                                  size: 38,
                                ),
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.fromLTRB(6, 0, 6, 9),
                        child: Text(
                          name,
                          maxLines: 2,
                          textAlign: TextAlign.center,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _resources(BuildContext context, Map<String, dynamic> data) {
    final resources = _maps(data['resources']);
    if (resources.isEmpty) {
      return _empty(
        context,
        Icons.folder_outlined,
        'Aucune ressource du contexte n’est disponible ici.',
      );
    }
    final route = _map(data['subject'])['route']?.toString();
    final opensJourney =
        route != null &&
        route.startsWith('/journeys/') &&
        widget.onOpenSubject != null;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 36),
      children: [
        Text(
          'Ressources du contexte',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        for (final resource in resources)
          ListTile(
            leading: const Icon(Icons.description_outlined),
            title: Text(resource['title']?.toString() ?? 'Ressource'),
            subtitle: Text(
              resource['description']?.toString().isNotEmpty == true
                  ? resource['description'].toString()
                  : 'Disponible selon les droits du contexte',
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            trailing: opensJourney
                ? const Icon(Icons.chevron_right_rounded)
                : null,
            onTap: opensJourney ? () => widget.onOpenSubject!(route) : null,
          ),
      ],
    );
  }

  Widget _settings(BuildContext context, Map<String, dynamic> data) {
    final state = _map(data['personal_state']);
    final created = DateTime.tryParse(data['created_at']?.toString() ?? '');
    final when = created == null
        ? ''
        : MaterialLocalizations.of(context).formatMediumDate(created.toLocal());
    final configuration = _map(data['configuration']);
    return ListView(
      key: const Key('conversation-details-settings-list'),
      padding: const EdgeInsets.fromLTRB(8, 12, 8, 48),
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
          child: Text(
            'Pour moi',
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        _setting(
          'mute',
          Icons.notifications_off_outlined,
          'Signaux',
          'Couper les signaux de cette conversation',
          state['muted'] == true,
          state,
        ),
        _setting(
          'pin',
          Icons.push_pin_outlined,
          'Épingler',
          'Retrouver cette conversation rapidement',
          state['pinned'] == true,
          state,
        ),
        _setting(
          'revisit',
          Icons.bookmark_border_rounded,
          'Revoir plus tard',
          'Conserver un repère personnel',
          state['revisit'] == true,
          state,
        ),
        const Divider(),
        _setting(
          'archive',
          Icons.archive_outlined,
          'Archiver',
          'Ranger pour moi, sans fermer pour les autres',
          state['archived'] == true,
          state,
        ),
        _setting(
          'hide',
          Icons.visibility_off_outlined,
          'Masquer',
          'Retirer de ma liste personnelle',
          state['hidden'] == true,
          state,
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        if (configuration.isNotEmpty) ...[
          const Divider(height: 32),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
            child: Text(
              'Fonctionnement de la conversation',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
          for (final entry in [
            ('Mode', configuration['mode']),
            ('Accès', configuration['entry']),
            ('Historique', configuration['history']),
            ('État', configuration['lifecycle']),
            ('Créée par', configuration['created_by']),
          ])
            if (entry.$2 != null && entry.$2.toString().trim().isNotEmpty)
              ListTile(
                dense: true,
                title: Text(entry.$1),
                subtitle: Text(entry.$2.toString()),
              ),
        ],
        if (when.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 24, 16, 4),
            child: Text(
              'Conversation créée le $when',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        if (data['share_requires_access'] == true)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Text(
              'Partager son lien ne donne aucun nouveau droit '
              'd’accès à cette conversation.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
      ],
    );
  }

  Widget _setting(
    String action,
    IconData icon,
    String title,
    String subtitle,
    bool enabled,
    Map<String, dynamic> state,
  ) => SwitchListTile(
    key: Key('conversation-detail-setting-$action'),
    value: enabled,
    onChanged: _busy == null ? (_) => _toggle(action, state) : null,
    secondary: Icon(icon),
    title: Text(title),
    subtitle: Text(subtitle),
  );

  Widget _empty(BuildContext context, IconData icon, String message) => Center(
    child: Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            icon,
            size: 38,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
          const SizedBox(height: 14),
          Text(
            message,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchDetail(widget.conversationId),
      builder: (context, snapshot) {
        final projection = snapshot.data;
        final data = projection?.payload;
        if (data == null) {
          return Scaffold(
            appBar: AppBar(title: const Text('Conversation')),
            body: Center(
              child: TextButton.icon(
                onPressed: _refresh,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Détails indisponibles · Réessayer'),
              ),
            ),
          );
        }
        final hasResources = _maps(data['resources']).isNotEmpty;
        final sections = <(String, IconData)>[
          (
            data['subject'] is Map && _map(data['subject'])['kind'] == 'group'
                ? 'Participants'
                : 'Participants',
            Icons.people_outline_rounded,
          ),
          ('Médias', Icons.perm_media_outlined),
          if (hasResources) ('Ressources', Icons.folder_outlined),
          ('Paramètres', Icons.tune_rounded),
        ];
        return DefaultTabController(
          length: sections.length,
          child: Scaffold(
            appBar: AppBar(title: const Text('Détails de la conversation')),
            body: NestedScrollView(
              headerSliverBuilder: (context, innerBoxIsScrolled) => [
                SliverToBoxAdapter(child: _hero(context, data)),
                SliverPersistentHeader(
                  pinned: true,
                  delegate: _ConversationDetailsTabHeader(
                    child: Material(
                      color: Theme.of(context).colorScheme.surface,
                      child: TabBar(
                        key: const Key('conversation-details-tabs'),
                        isScrollable: sections.length > 3,
                        tabs: [
                          for (final (label, icon) in sections)
                            Tab(text: label, icon: Icon(icon, size: 20)),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
              body: TabBarView(
                children: [
                  _members(context, data),
                  _media(context, data),
                  if (hasResources) _resources(context, data),
                  _settings(context, data),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const {};
}

List<Map<String, dynamic>> _maps(Object? value) {
  if (value is! List) return const [];
  return value
      .map(_map)
      .where((value) => value.isNotEmpty)
      .toList(growable: false);
}

class _ConversationDetailsTabHeader extends SliverPersistentHeaderDelegate {
  const _ConversationDetailsTabHeader({required this.child});

  final Widget child;

  @override
  double get minExtent => 72;

  @override
  double get maxExtent => 72;

  @override
  Widget build(
    BuildContext context,
    double shrinkOffset,
    bool overlapsContent,
  ) => child;

  @override
  bool shouldRebuild(covariant _ConversationDetailsTabHeader oldDelegate) =>
      oldDelegate.child != child;
}
