import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:terraguavd_field/main.dart';

void main() {
  testWidgets('field login retains safety wording and requires credentials', (tester) async {
    await tester.pumpWidget(const TerraGuavdField());
    expect(find.text('Field Personnel sign in'), findsOneWidget);
    expect(find.textContaining('Surveyed does not mean cleared or safe.'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pump();
    expect(find.text('Enter username and password.'), findsOneWidget);
  });
}
