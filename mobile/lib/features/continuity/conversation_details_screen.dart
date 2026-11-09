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

  Future<void> _openAttachment(
    Map<String, dynamic> attachment, {
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
          initialIndex: gallery.indexWhere(
            (item) => item['id'] == attachment['id'],
          ),
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

  Future<void> _inviteByIdentifier() async {
    final input = TextEditingController();
    var kind = 'profile';
    var candidates = <Map<String, dynamic>>[];
    var searching = false;
    var sending = false;
    var generation = 0;
    String? error;
    final changed = ValueNotifier<int>(0);
    Future<void> search() async {
      final q = input.text.trim();
      final request = ++generation;
      if (q.length < 2) {
        candidates = [];
        changed.value++;
        return;
      }
      searching = true;
      changed.value++;
      try {
        final results = await widget.repository.searchInvitationCandidates(
          conversationId: widget.conversationId, query: q,
        );
        if (request == generation) {
          candidates = results;
          searching = false;
          changed.value++;
        }
      } on Object {
        if (request == generation) {
          searching = false;
          error = 'Suggestions indisponibles. Utilisez un identifiant exact.';
          changed.value++;
        }
      }
    }

    try {
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        showDragHandle: true,
        builder: (sheetContext) => Padding(
          padding: EdgeInsets.only(
            bottom: MediaQuery.viewInsetsOf(sheetContext).bottom,
          ),
          child: ValueListenableBuilder<int>(
            valueListenable: changed,
            builder: (sheetContext, _, child) => SizedBox(
              height: MediaQuery.sizeOf(sheetContext).height * .72,
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text('Inviter par identifiant Makolo',
                        style: Theme.of(sheetContext).textTheme.titleLarge),
                    const SizedBox(height: 8),
                    Text(
                      'Aucun contact obligatoire. Les noms sont des indications : '
                      'seul le username ou slug exact sera utilisé.',
                      style: Theme.of(sheetContext).textTheme.bodySmall,
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: kind,
                      decoration: const InputDecoration(
                        labelText: 'Type', border: OutlineInputBorder(),
                      ),
                      items: const [
                        DropdownMenuItem(value: 'profile', child: Text('Profil')),
                        DropdownMenuItem(value: 'space', child: Text('Espace')),
                        DropdownMenuItem(value: 'group', child: Text('Groupe')),
                      ],
                      onChanged: sending ? null : (value) {
                        kind = value ?? 'profile';
                        changed.value++;
                      },
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: input,
                      enabled: !sending,
                      maxLength: 200,
                      autocorrect: false,
                      decoration: const InputDecoration(
                        labelText: 'Identifiant Makolo',
                        hintText: 'username ou slug',
                        prefixIcon: Icon(Icons.alternate_email_rounded),
                        border: OutlineInputBorder(),
                      ),
                      onChanged: (_) {
                        error = null;
                        search();
                      },
                    ),
                    if (searching)
                      const LinearProgressIndicator(minHeight: 2),
                    if (error != null)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Text(error!, style: TextStyle(
                          color: Theme.of(sheetContext).colorScheme.error,
                        )),
                      ),
                    Expanded(
                      child: ListView(
                        children: [
                          for (final candidate in candidates)
                            if (candidate['kind'] == kind)
                              ListTile(
                                title: Text(candidate['label']?.toString() ?? 'Makolo'),
                                subtitle: Text(candidate['description']?.toString() ??
                                  candidate['identifier']?.toString() ?? ''),
                                onTap: sending ? null : () {
                                  kind = candidate['kind']?.toString() ?? kind;
                                  input.text = candidate['identifier']?.toString() ?? '';
                                  candidates = [];
                                  changed.value++;
                                },
                              ),
                          if (!searching && candidates.isEmpty)
                            const Padding(
                              padding: EdgeInsets.symmetric(vertical: 16),
                              child: Text(
                                'Saisissez un identifiant exact connu, ou '
                                'recherchez un Profil, Espace ou Groupe découvrable.',
                              ),
                            ),
                        ],
                      ),
                    ),
                    FilledButton.icon(
                      onPressed: sending || input.text.trim().isEmpty ? null : () async {
                        sending = true;
                        error = null;
                        changed.value++;
                        try {
                          await widget.repository.inviteIdentifier(
                            conversationId: widget.conversationId,
                            kind: kind, identifier: input.text.trim(),
                          );
                          if (sheetContext.mounted) Navigator.of(sheetContext).pop();
                          if (mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text(
                                'Invitation enregistrée. Une acceptation est nécessaire.',
                              )),
                            );
                          }
                        } on Object {
                          error = 'Invitation non confirmée. Vérifiez l’identifiant '
                            'et les règles de confidentialité.';
                        } finally {
                          sending = false;
                          changed.value++;
                        }
                      },
                      icon: const Icon(Icons.person_add_alt_rounded),
                      label: Text(sending ? 'Envoi…' : 'Envoyer une invitation'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    } finally {
      ++generation;
      input.dispose();
      changed.dispose();
    }
  }

  Future<void> _manageParticipant(String operation, String resourceId) async {
    if (_busy != null) return;
    final approved = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Confirmer cette modification ?'),
        content: const Text(
          'Les droits de participation sont recalculés côté serveur. '
          'Un accès issu du contexte peut continuer d’exister.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Confirmer'),
          ),
        ],
      ),
    );
    if (!mounted || approved != true) return;
    setState(() { _busy = operation; _error = null; });
    try {
      await widget.repository.manageConversationParticipant(
        conversationId: widget.conversationId,
        operation: operation, resourceId: resourceId,
      );
    } on Object {
      if (mounted) setState(() => _error =
        'Action non confirmée. Actualisez les participants.');
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  Future<void> _openJoinRequests() async {
    if (_busy != null) return;
    List<Map<String, dynamic>> entries;
    try {
      entries = await widget.repository.conversationJoinRequests(
        widget.conversationId,
      );
    } on Object {
      if (mounted) setState(() => _error = 'Demandes d’entrée indisponibles.');
      return;
    }
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true, useSafeArea: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, refresh) => ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text('Demandes d’entrée',
                style: Theme.of(sheetContext).textTheme.titleLarge),
            for (final row in entries)
              ListTile(
                title: Text(row['label']?.toString() ?? 'Profil'),
                subtitle: Text('@${row['identifier'] ?? ''}'),
                trailing: Wrap(
                  spacing: 6,
                  children: [
                    TextButton(
                      onPressed: () async {
                        try {
                          await widget.repository.decideJoinRequest(
                            conversationId: widget.conversationId,
                            requestId: row['id'].toString(), approve: false,
                          );
                          entries.remove(row);
                          refresh(() {});
                        } on Object { /* Owner state unchanged. */ }
                      },
                      child: const Text('Refuser'),
                    ),
                    FilledButton(
                      onPressed: () async {
                        try {
                          await widget.repository.decideJoinRequest(
                            conversationId: widget.conversationId,
                            requestId: row['id'].toString(), approve: true,
                          );
                          entries.remove(row);
                          refresh(() {});
                        } on Object { /* Owner state unchanged. */ }
                      },
                      child: const Text('Accepter'),
                    ),
                  ],
                ),
              ),
            if (entries.isEmpty) const ListTile(
              title: Text('Aucune demande en attente'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _selfEntry(String action) async {
    if (_busy != null) return;
    setState(() { _busy = action; _error = null; });
    try {
      await widget.repository.conversationSelfEntry(
        conversationId: widget.conversationId, action: action,
      );
    } on Object {
      if (mounted) setState(() => _error =
        'Demande non confirmée. Actualisez pour connaître votre état.');
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  Widget _members(BuildContext context, Map<String, dynamic> data) {
    final members = _map(data['members']);
    final people = _maps(members['people']);
    final invitations = _maps(members['invitations']);
    final collectives = _maps(members['collectives']);
    final derived = _map(members['derived']);
    final manage = members['can_manage'] == true || data['can_manage'] == true;
    final restricted = members['scope'] == 'restricted';
    final colors = Theme.of(context).colorScheme;
    return ListView(
      key: const Key('conversation-details-members-list'),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 36),
      children: [
        if (manage) ...[
          FilledButton.icon(
            key: const Key('conversation-invite-identifier'),
            onPressed: _busy != null ? null : _inviteByIdentifier,
            icon: const Icon(Icons.person_add_alt_rounded),
            label: const Text('Ajouter avec un identifiant Makolo'),
          ),
          const SizedBox(height: 10),
          Text(
            'Aucun contact obligatoire. L’invitation attend l’acceptation '
            'du Profil ou d’un responsable du collectif.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 18),
        ],
        if (data['can_join'] == true || data['can_request_entry'] == true ||
            data['entry_request_status'] == 'pending') ...[
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (data['can_join'] == true)
                FilledButton.tonal(
                  onPressed: _busy != null ? null : () => _selfEntry('join'),
                  child: const Text('Rejoindre'),
                ),
              if (data['can_request_entry'] == true)
                OutlinedButton(
                  onPressed: _busy != null ? null : () => _selfEntry('request'),
                  child: const Text('Demander à rejoindre'),
                ),
              if (data['entry_request_status'] == 'pending')
                const Chip(label: Text('Demande en attente')),
            ],
          ),
          const SizedBox(height: 14),
        ],
        Text('Participants',
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        if (restricted)
          ListTile(
            leading: const Icon(Icons.lock_outline_rounded),
            title: const Text('Liste privée'),
            subtitle: Text(
              members['explanation']?.toString() ??
                'Les personnes concernées dépendent du contexte.',
            ),
          )
        else ...[
          if (people.isEmpty)
            const ListTile(
              title: Text('Aucune participation explicite à afficher'),
            ),
          for (final member in people)
            ListTile(
              leading: CircleAvatar(
                backgroundColor: colors.primaryContainer,
                child: const Icon(Icons.person_outline_rounded),
              ),
              title: Text(member['label']?.toString() ?? 'Profil'),
              subtitle: Text(
                '@${member['identifier'] ?? ''}' +
                (member['is_me'] == true ? ' · Vous' : ''),
              ),
              trailing: manage && member['participation_id'] != null
                  ? IconButton(
                      tooltip: 'Retirer cette participation explicite',
                      onPressed: _busy != null ? null : () =>
                          _manageParticipant(
                            'remove', member['participation_id'].toString(),
                          ),
                      icon: const Icon(Icons.person_remove_outlined),
                    )
                  : null,
            ),
        ],
        if (derived.isNotEmpty) ...[
          const Divider(height: 24),
          ListTile(
            leading: const Icon(Icons.groups_outlined),
            title: Text(derived['label']?.toString() ?? 'Groupe'),
            subtitle: Text(
              'Accès dérivé du Groupe · ${derived['identifier'] ?? ''}. '
              'Il ne crée aucune participation explicite.',
            ),
          ),
        ],
        if (manage) ...[
          const Divider(height: 26),
          Text('Invitations individuelles',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          if (invitations.isEmpty)
            const ListTile(title: Text('Aucune invitation en attente')),
          for (final item in invitations)
            ListTile(
              leading: const Icon(Icons.mark_email_unread_outlined),
              title: Text('@${item['identifier'] ?? ''}'),
              subtitle: Text(item['status']?.toString() ?? 'En attente'),
              trailing: item['status'] == 'pending'
                  ? TextButton(
                      onPressed: _busy != null ? null : () =>
                          _manageParticipant('cancel', item['id'].toString()),
                      child: const Text('Annuler'),
                    )
                  : null,
            ),
          const Divider(height: 26),
          Text('Espaces et Groupes',
              style: Theme.of(context).textTheme.titleMedium),
          Text(
            'Les membres actuels sont dérivés après acceptation du collectif.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          if (collectives.isEmpty)
            const ListTile(title: Text('Aucun collectif invité')),
          for (final item in collectives)
            ListTile(
              leading: Icon(item['kind'] == 'space'
                  ? Icons.apartment_rounded : Icons.groups_rounded),
              title: Text(item['label']?.toString() ?? 'Collectif'),
              subtitle: Text('${item['identifier'] ?? ''} · '
                  '${item['status'] ?? ''}'),
              trailing: item['status'] == 'pending' ||
                      item['status'] == 'active'
                  ? TextButton(
                      onPressed: _busy != null ? null : () =>
                          _manageParticipant('revoke', item['id'].toString()),
                      child: const Text('Retirer'),
                    )
                  : null,
            ),
          const SizedBox(height: 14),
          OutlinedButton.icon(
            onPressed: _busy != null ? null : _openJoinRequests,
            icon: const Icon(Icons.person_search_outlined),
            label: const Text('Gérer les demandes d’entrée'),
          ),
        ],
        if (people.any((item) => item['is_me'] == true &&
            item['participation_id'] != null)) ...[
          const SizedBox(height: 18),
          OutlinedButton(
            onPressed: _busy != null ? null : () async {
              setState(() => _busy = 'leave');
              try {
                await widget.repository.conversationSelfEntry(
                  conversationId: widget.conversationId, action: 'leave',
                );
              } on Object {
                if (mounted) setState(() =>
                  _error = 'Sortie non confirmée. Vérifiez votre accès.');
              } finally {
                if (mounted) setState(() => _busy = null);
              }
            },
            child: const Text('Quitter ma participation explicite'),
          ),
        ],
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Text(_error!, style: TextStyle(color: colors.error)),
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
                                      : attachment['mime_type'] ==
                                            'application/pdf'
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
