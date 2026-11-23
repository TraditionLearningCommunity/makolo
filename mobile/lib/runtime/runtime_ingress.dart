import 'dart:async';

import '../navigation/incoming_intent.dart';
import '../platform/sharing/system_share_receiver.dart';

/// Ephemeral navigation ingress. Shared content is never persisted here:
/// Mark copies the selected files into its Profile-scoped local draft owner.
class RuntimeIngress {
  RuntimeIngress();

  final StreamController<IncomingIntent> _controller =
      StreamController<IncomingIntent>.broadcast();
  final StreamController<void> _shareChanges =
      StreamController<void>.broadcast();

  final List<({SharedPayload payload, String? profileId})> _shares = [];

  Stream<IncomingIntent> get intents => _controller.stream;
  Stream<void> get sharesChanged => _shareChanges.stream;
  bool get hasPendingShare => _shares.isNotEmpty;

  void add(IncomingIntent intent) => _controller.add(intent);

  void offerShare(SharedPayload payload, {String? profileId}) {
    // Bound the temporary memory queue; oldest entries are never copied to
    // a new Profile after an account switch.
    if (_shares.length >= 5) _shares.removeAt(0);
    _shares.add((payload: payload, profileId: profileId));
    _shareChanges.add(null);
  }

  SharedPayload? takeShare({required String profileId}) {
    while (_shares.isNotEmpty) {
      final next = _shares.removeAt(0);
      if (next.profileId == null || next.profileId == profileId) {
        return next.payload;
      }
    }
    return null;
  }

  void discardShares() {
    _shares.clear();
  }

  Future<void> close() async {
    _shares.clear();
    await _shareChanges.close();
    await _controller.close();
  }
}
