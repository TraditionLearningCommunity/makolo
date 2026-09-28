import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

class ResumableInteractionStore {
  ResumableInteractionStore._(this._file, this._memory);

  factory ResumableInteractionStore.memory() =>
      ResumableInteractionStore._(null, <String, dynamic>{});

  static const _fileName = 'makolo-resumable-interactions-v1.json';
  static const _sensitiveFragments = <String>{
    'password',
    'passcode',
    'token',
    'secret',
    'credential',
    'refresh',
    'access_token',
  };

  final File? _file;
  final Map<String, dynamic>? _memory;

  static Future<ResumableInteractionStore> open() async {
    final directory = await getApplicationSupportDirectory();
    return ResumableInteractionStore._(
      File('${directory.path}${Platform.pathSeparator}$_fileName'),
      null,
    );
  }

  Future<Map<String, dynamic>> read(String interactionId) async {
    final all = await _readAll();
    final value = all[interactionId];
    if (value is! Map) return const {};
    return Map<String, dynamic>.from(value);
  }

  Future<void> save(String interactionId, Map<String, dynamic> values) async {
    final safe = <String, dynamic>{};
    for (final entry in values.entries) {
      final normalized = entry.key.toLowerCase();
      if (_sensitiveFragments.any(normalized.contains)) continue;
      final value = entry.value;
      if (value == null || value is String || value is num || value is bool) {
        safe[entry.key] = value;
      }
    }

    final all = await _readAll();
    if (safe.isEmpty) {
      all.remove(interactionId);
    } else {
      all[interactionId] = safe;
    }
    await _writeAll(all);
  }

  Future<void> clear(String interactionId) async {
    final all = await _readAll();
    if (all.remove(interactionId) != null) {
      await _writeAll(all);
    }
  }

  Future<Map<String, dynamic>> _readAll() async {
    final memory = _memory;
    if (memory != null) return Map<String, dynamic>.from(memory);
    final file = _file!;
    if (!await file.exists()) return {};
    try {
      final decoded = jsonDecode(await file.readAsString());
      if (decoded is! Map) return {};
      return Map<String, dynamic>.from(decoded);
    } on Object {
      return {};
    }
  }

  Future<void> _writeAll(Map<String, dynamic> values) async {
    final memory = _memory;
    if (memory != null) {
      memory
        ..clear()
        ..addAll(values);
      return;
    }
    final file = _file!;
    await file.parent.create(recursive: true);
    await file.writeAsString(jsonEncode(values), flush: true);
  }
}
