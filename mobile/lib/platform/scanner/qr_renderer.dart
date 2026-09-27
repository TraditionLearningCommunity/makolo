import 'package:flutter/widgets.dart';
import 'package:qr_flutter/qr_flutter.dart';

class MakoloQrView extends StatelessWidget {
  const MakoloQrView({
    required this.payload,
    this.size = 220,
    super.key,
  });

  final String payload;
  final double size;

  @override
  Widget build(BuildContext context) {
    return QrImageView(
      data: payload,
      version: QrVersions.auto,
      size: size,
    );
  }
}
