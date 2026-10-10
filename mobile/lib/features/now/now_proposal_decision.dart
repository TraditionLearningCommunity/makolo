import 'dart:async';

import 'package:flutter/material.dart';

import '../../network/makolo_api_client.dart';
import '../../presentation/contracts/now_presentation.dart';

/// Focused decision owned by Action Network, including explicit Space context.
/// No local authority can be inferred from Membership or the action label.
class NowProposalDecision extends StatefulWidget {
  const NowProposalDecision({
    super.key,
    required this.situation,
    required this.action,
    required this.api,
    this.onRefresh,
  });

  final NowSituationPresentation situation;
  final NowBusinessActionPresentation action;
  final MakoloApiClient api;
  final Future<void> Function()? onRefresh;

  static final RegExp _uuid = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  static String? authorizedPath(
    NowSituationPresentation situation,
    NowBusinessActionPresentation action,
  ) {
    final owner = situation.ownerDestination;
    if (owner == null ||
        owner.kind.toLowerCase() != 'action_proposal' ||
        !_uuid.hasMatch(owner.id) ||
        action.capability != 'respond' ||
        action.interactionDepth != NowInteractionDepth.focused) {
      return null;
    }
    final expected = '/api/v1/social/action-proposals/${owner.id}/respond/';
    return action.href == expected ? expected.substring(1) : null;
  }

  @override
  State<NowProposalDecision> createState() => _NowProposalDecisionState();
}

class _NowProposalDecisionState extends State<NowProposalDecision> {
  bool _sending = false;
  bool _confirmed = false;
  String? _error;

  Future<void> _respond() async {
    final postPath = NowProposalDecision.authorizedPath(
      widget.situation,
      widget.action,
    );
    if (postPath == null || _sending || _confirmed) return;
    final ownerId = widget.situation.ownerDestination!.id;
    setState(() {
      _sending = true;
      _error = null;
    });

    try {
      // Re-read the canonical owner, not a cached Now capability.
      final read = await widget.api.get(
        'api/v1/social/action-proposals/$ownerId/',
      );
      final data = read.jsonObject();
      final identity = data['identity'];
      final capabilities = data['capabilities'];
      final links = data['links'];
      final actor = data['acting_context'];
      if (identity is! Map ||
          identity['kind'] != 'action_proposal' ||
          identity['id']?.toString().toLowerCase() != ownerId.toLowerCase() ||
          data['state'] != 'pending' ||
          capabilities is! List ||
          !capabilities.contains('respond') ||
          links is! Map ||
          links['respond'] != '/$postPath' ||
          actor is! Map) {
        throw StateError('Owner capability changed.');
      }

      final contextKind = actor['kind'];
      final contextId = actor['id']?.toString();
      final isSpace = contextKind == 'space' && actor['explicit'] == true;
      if (contextKind != 'profile' && !isSpace) {
        throw StateError('Explicit actor context is unavailable.');
      }
      if (isSpace &&
          (contextId == null ||
              !NowProposalDecision._uuid.hasMatch(contextId))) {
        throw StateError('Space authority context is missing.');
      }
      if (!mounted) return;
      final title = isSpace
          ? 'Réponse au nom de ${actor['name'] ?? 'cet Espace'}'
          : 'Réponse personnelle';
      final decision = await showDialog<String>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text(title),
          content: Text(
            isSpace
                ? 'Vous allez répondre au nom de cet Espace. '
                      'Le serveur vérifiera votre Mandate et vos permissions.'
                : 'Vous allez répondre personnellement. '
                      'La décision sera vérifiée par le propriétaire.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('Annuler'),
            ),
            OutlinedButton(
              onPressed: () => Navigator.of(dialogContext).pop('declined'),
              child: const Text('Refuser'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop('accepted'),
              child: const Text('Accepter'),
            ),
          ],
        ),
      );
      if (!mounted || decision == null) return;

      final response = await widget.api.post(
        postPath,
        body: {'status': decision, if (isSpace) 'acting_space_id': contextId},
      );
      final answer = response.jsonObject();
      final returnedIdentity = answer['identity'];
      if (response.statusCode != 200 ||
          returnedIdentity is! Map ||
          returnedIdentity['id']?.toString().toLowerCase() !=
              ownerId.toLowerCase() ||
          answer['state'] != decision) {
        throw StateError('Owner did not confirm the decision.');
      }
      if (!mounted) return;
      setState(() => _confirmed = true);
      try {
        await widget.onRefresh?.call();
      } on Object {
        // The owner confirmation is retained while Now refreshes later.
      }
    } on Object {
      if (mounted) {
        setState(
          () => _error =
              'La décision n’a pas été confirmée. '
              'Consultez la proposition avant de réessayer.',
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      FilledButton.icon(
        onPressed: _sending || _confirmed ? null : () => unawaited(_respond()),
        icon: const Icon(Icons.arrow_forward_rounded),
        label: Text(widget.action.label),
      ),
      if (_sending) const LinearProgressIndicator(),
      if (_confirmed) const Text('Réponse confirmée par le réseau d’action.'),
      if (_error != null)
        Text(
          _error!,
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
    ],
  );
}
