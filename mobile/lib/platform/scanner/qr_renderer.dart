import 'package:flutter/widgets.dart';
import 'package:pretty_qr_code/pretty_qr_code.dart';

class MakoloQrView extends StatelessWidget {
  const MakoloQrView({required this.payload, this.size = 220, super.key});

  final String payload;
  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox.square(
      dimension: size,
      child: PrettyQrView.data(data: payload),
    );
  }
}
