import 'dart:convert';

import 'package:build/build.dart';
import 'package:dart_style/dart_style.dart';

Builder meFormatProbe(BuilderOptions options) => _MeFormatProbe();

class _MeFormatProbe implements Builder {
  @override
  Map<String, List<String>> get buildExtensions => const {
    '.dart': ['.meprobe'],
  };

  @override
  Future<void> build(BuildStep buildStep) async {
    final source = await buildStep.readAsString(buildStep.inputId);
    final formatted = DartFormatter(
      languageVersion: DartFormatter.latestLanguageVersion,
    ).format(source);
    final encoded = base64Encode(utf8.encode(formatted));
    const chunkSize = 4000;
    final total = (encoded.length / chunkSize).ceil();

    for (var index = 0; index < total; index++) {
      final start = index * chunkSize;
      final end = (start + chunkSize < encoded.length)
          ? start + chunkSize
          : encoded.length;
      log.warning(
        'MEFORMAT|\${buildStep.inputId.path}|\$index|\$total|'
        '\${encoded.substring(start, end)}',
      );
    }

    await buildStep.writeAsString(
      buildStep.inputId.changeExtension('.meprobe'),
      'probe',
    );
  }
}
