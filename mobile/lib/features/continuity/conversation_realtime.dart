import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import '../../network/makolo_api_client.dart';

/// One adapter per authenticated repository. REST remains the mutation owner.
class ConversationRealtime {
  ConversationRealtime({
    required this.api,
    required this.profileId,
    required this.onChanged,
    required this.onRevoked,
  });
  final MakoloApiClient api;
  final String profileId;
  final Future<void> Function(String pointId) onChanged;
  final Future<void> Function(String pointId) onRevoked;
  final _signals = StreamController<Map<String, dynamic>>.broadcast();
  Stream<Map<String, dynamic>> get signals => _signals.stream;
  final Map<String, int> _points = {};
  WebSocket? _socket;
  StreamSubscription<dynamic>? _subscription;
  Timer? _retry;
  Timer? _heartbeat;
  bool _disposed = false;
  bool _connecting = false;
  bool _foreground = true;
  bool _authenticated = false;
  int _attempt = 0;
  int _generation = 0;

  void acquire(String pointId) {
    _points[pointId] = (_points[pointId] ?? 0) + 1;
    if (_authenticated) _send('subscribe', pointId);
    _connect();
  }

  void release(String pointId) {
    final count = (_points[pointId] ?? 1) - 1;
    if (count > 0) {
      _points[pointId] = count;
      return;
    }
    _points.remove(pointId);
    _send('unsubscribe', pointId);
    if (_points.isEmpty) _stop();
  }

  void _send(String type, [String? pointId]) {
    if (!_authenticated || _socket?.readyState != WebSocket.open) return;
    _socket!.add(
      jsonEncode({'type': type, if (pointId != null) 'point_id': pointId}),
    );
  }

  void typing(String pointId) => _send('typing', pointId);

  void foreground(bool value) {
    _foreground = value;
    if (!value) {
      _stop();
      return;
    }
    for (final point in _points.keys) {
      unawaited(_refresh(point));
    }
    _connect();
  }

  Future<void> _refresh(String point) async {
    try {
      await onChanged(point);
    } on Object {
      _signals.add({'type': 'sync_unavailable', 'point_id': point});
    }
  }

  Future<void> _connect() async {
    if (_disposed ||
        !_foreground ||
        _points.isEmpty ||
        _connecting ||
        _socket != null)
      return;
    _connecting = true;
    final generation = _generation;
    try {
      final response = await api.post(
        'api/v1/conversations/realtime-ticket/',
        headers: {'X-Makolo-Profile': profileId},
        body: {},
      );
      final ticket = response.jsonObject();
      if (ticket['profile_id'] != profileId)
        throw const FormatException('Realtime Profile changed');
      final base = api.baseUri;
      final path = ticket['websocket_path'];
      if (path is! String ||
          !path.startsWith('/') ||
          path.startsWith('//') ||
          ticket['ticket'] is! String) {
        throw const FormatException('Invalid realtime ticket');
      }
      final uri = base
          .resolve(path)
          .replace(scheme: base.scheme == 'https' ? 'wss' : 'ws');
      // A native client has no browser Origin. Send the actual API origin so
      // it passes the same allow-list as Web, without inventing a separate host.
      final socket = await WebSocket.connect(
        uri.toString(),
        headers: {'Origin': base.origin},
      ).timeout(const Duration(seconds: 5));
      if (_disposed ||
          generation != _generation ||
          !_foreground ||
          _points.isEmpty) {
        await socket.close();
        return;
      }
      _socket = socket;
      socket.add(
        jsonEncode({'type': 'authenticate', 'ticket': ticket['ticket']}),
      );
      _subscription = socket.listen(
        (dynamic raw) {
          if (raw is! String) return;
          try {
            final value = jsonDecode(raw);
            if (value is! Map<String, dynamic>) return;
            if (value['type'] == 'authenticated') {
              _authenticated = true;
              _attempt = 0;
              for (final point in _points.keys) {
                _send('subscribe', point);
                unawaited(_refresh(point));
              }
            }
            final point = value['point_id'];
            if (point is String && _points.containsKey(point)) {
              if (value['type'] == 'point_changed') unawaited(_refresh(point));
              if (value['type'] == 'receipt_changed')
                unawaited(_refresh(point));
              if (value['code'] == 'access_revoked')
                unawaited(onRevoked(point));
              _signals.add(value);
            }
          } on FormatException {
            unawaited(socket.close());
          }
        },
        onError: (Object error) {
          _lost();
        },
        onDone: _lost,
        cancelOnError: true,
      );
      _heartbeat = Timer.periodic(const Duration(seconds: 20), (_) {
        _send('ping');
        for (final point in _points.keys) _send('presence', point);
      });
    } on Object {
      if (!_disposed) _signals.add({'type': 'transport_unavailable'});
      _schedule();
    } finally {
      _connecting = false;
    }
  }

  void _lost() {
    _authenticated = false;
    _socket = null;
    _heartbeat?.cancel();
    _schedule();
  }

  void _schedule() {
    _retry?.cancel();
    if (_disposed || !_foreground || _points.isEmpty) return;
    final seconds = min(60, pow(2, min(_attempt++, 6)).toInt());
    _retry = Timer(
      Duration(
        milliseconds: (seconds * 1000 * (.75 + Random().nextDouble() / 2))
            .round(),
      ),
      _connect,
    );
  }

  void _stop() {
    _generation++;
    _retry?.cancel();
    _heartbeat?.cancel();
    _authenticated = false;
    unawaited(_subscription?.cancel());
    _subscription = null;
    unawaited(_socket?.close());
    _socket = null;
  }

  Future<void> dispose() async {
    _disposed = true;
    _points.clear();
    _stop();
    await _signals.close();
  }
}
