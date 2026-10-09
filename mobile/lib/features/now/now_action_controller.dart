import 'dart:async';

import 'package:flutter/material.dart';

import '../../network/makolo_api_client.dart';
import '../../presentation/contracts/now_presentation.dart';

/// Only the existing owner service may authorize and confirm a mutation.
/// Presentation never turns a capability or a URL into a generic HTTP action.
abstract final class NowOwnerAction {
  static final RegExp _uuid = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  static String? authorizedPath(
    NowSituationPresentation situation,
    NowBusinessActionPresentation action,
  ) {
    if (action.interactionDepth != NowInteractionDepth.directNow ||
        !action.confirmationRequired) {
      return null;
    }
    final owner = situation.ownerDestination;
    final raw = action.href;
    if (owner == null || raw == null || !_uuid.hasMatch(owner.id)) return null;

    final capability = action.capability;
    final prefix = switch (owner.kind.toLowerCase()) {
      'recognition_redemption'
          when capability == 'accept' || capability == 'decline' =>
        '/api/v1/recognition/redemptions/',
      'waitlist' when capability == 'accept' || capability == 'leave' =>
        '/api/v1/tickets/waitlist/',
      'ticket_transfer'
          when capability == 'accept' || capability == 'decline' =>
        '/api/v1/tickets/transfers/',
      _ => null,
    };
    if (prefix == null) return null;
    final expected = '$prefix${owner.id}/$capability/';
    final url = Uri.tryParse(raw);
    if (url == null ||
        url.hasScheme ||
        url.hasAuthority ||
        url.hasQuery ||
        url.hasFragment ||
        raw != expected) {
      return null;
    }
    return expected.substring(1);
  }

  static Future<void> commit({
    required NowSituationPresentation situation,
    required NowBusinessActionPresentation action,
    required MakoloApiClient api,
  }) async {
    final path = authorizedPath(situation, action);
    if (path == null) {
      throw StateError('Owner mutation contract is unavailable.');
    }
    // A one-shot command, never silently queued or blindly replayed. Every
    // destination is a concrete existing owner endpoint with a server-side
    // permission and lifecycle check.
    final response = await api.post(path);
    if (response.statusCode != 200) {
      throw StateError('Owner did not confirm the requested decision.');
    }
    final data = response.jsonObject();
    final id = data['id']?.toString();
    final owner = situation.ownerDestination!;
    if (owner.kind.toLowerCase() == 'waitlist' &&
        action.capability == 'accept') {
      // The ticket owner returns the newly reserved Order, not the Waitlist
      // entry. Payment may still be due: do not claim that it was completed.
      if (id == null ||
          !_uuid.hasMatch(id) ||
          data['status'] is! String) {
        throw StateError('Owner did not return a reserved Order.');
      }
    } else if (id?.toLowerCase() != owner.id.toLowerCase()) {
      throw StateError('Owner did not confirm this resource.');
    }
  }
}

/// The sync runtime is injected by the real Now route, not constructed by UI.
/// Widget tests and the Gallery remain independent of any live backend.
class NowActionRefreshScope extends InheritedWidget {
  const NowActionRefreshScope({
    super.key,
    required this.onRefresh,
    required super.child,
  });

  final Future<void> Function() onRefresh;

  static Future<void> Function()? maybeOf(BuildContext context) => context
      .dependOnInheritedWidgetOfExactType<NowActionRefreshScope>()
      ?.onRefresh;

  @override
  bool updateShouldNotify(NowActionRefreshScope oldWidget) =>
      oldWidget.onRefresh != onRefresh;
}

class NowActionGroup extends StatefulWidget {
  const NowActionGroup({
    super.key,
    required this.situation,
    required this.api,
    this.onOpenOwner,
  });

  final NowSituationPresentation situation;
  final MakoloApiClient? api;
  final VoidCallback? onOpenOwner;

  @override
  State<NowActionGroup> createState() => _NowActionGroupState();
}

class _NowActionGroupState extends State<NowActionGroup> {
  bool _sending = false;
  bool _confirmedByOwner = false;
  String? _error;

  @override
  void didUpdateWidget(covariant NowActionGroup oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.situation.identity != widget.situation.identity) {
      _error = null;
      _confirmedByOwner = false;
    }
  }

  Future<void> _execute(NowBusinessActionPresentation action) async {
    final api = widget.api;
    if (api == null || _sending || _confirmedByOwner) return;
    final path = NowOwnerAction.authorizedPath(widget.situation, action);
    if (path == null) return;

    final approved = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Confirmer votre décision'),
        content: Text(
          'Voulez-vous vraiment « ${action.label} » ? '
          'Cette décision sera envoyée au propriétaire de la demande.',
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
    if (approved != true || !mounted) return;

    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await NowOwnerAction.commit(
        situation: widget.situation,
        action: action,
        api: api,
      );
      if (!mounted) return;
      setState(() => _confirmedByOwner = true);
      final reproject = NowActionRefreshScope.maybeOf(context);
      if (reproject != null) {
        try {
          await reproject();
        } on Object {
          // The successful owner response is real; keep that truth while
          // waiting for a subsequent local-first reprojection.
        }
      }
    } on Object {
      if (!mounted) return;
      setState(() {
        _error =
            'Cette décision n’a pas été confirmée. '
            'Vérifiez son état dans la démarche avant de réessayer.';
      });
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final actions = widget.situation.businessActions
        .where(
          (action) =>
              action.isPresentationAction &&
              action.interactionDepth != NowInteractionDepth.none &&
              action.interactionDepth != NowInteractionDepth.unknown,
        )
        .toList(growable: false);
    if (actions.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var index = 0; index < actions.length; index++) ...[
          if (index != 0) const SizedBox(height: 8),
          Builder(
            builder: (context) {
              final action = actions[index];
              final direct =
                  widget.api != null &&
                  NowOwnerAction.authorizedPath(widget.situation, action) !=
                      null;
              final canHandoff = widget.onOpenOwner != null;
              final active =
                  !_sending && !_confirmedByOwner && (direct || canHandoff);
              if (!direct && !canHandoff) {
                return Text(
                  action.label,
                  style: Theme.of(context).textTheme.titleMedium,
                );
              }
              final VoidCallback? callback = !active
                  ? null
                  : direct
                  ? () => unawaited(_execute(action))
                  : widget.onOpenOwner;
              if (index == 0) {
                return FilledButton.icon(
                  onPressed: callback,
                  icon: const Icon(Icons.arrow_forward_rounded),
                  label: Text(action.label),
                );
              }
              return OutlinedButton(
                onPressed: callback,
                child: Text(action.label),
              );
            },
          ),
        ],
        if (_sending) ...[
          const SizedBox(height: 8),
          const LinearProgressIndicator(),
          const Text('Envoi de votre décision au propriétaire…'),
        ],
        if (_confirmedByOwner) ...[
          const SizedBox(height: 8),
          const Text('Décision confirmée par le propriétaire.'),
        ],
        if (_error != null) ...[
          const SizedBox(height: 8),
          Text(
            _error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ],
      ],
    );
  }
}
