'use strict';
const test_desc = 'Service gets removed. Reject with InvalidStateError.';
const expected =
    new DOMException('GATT Service no longer exists.', 'InvalidStateError');
let descriptor, fake_peripheral, fake_service;

bluetooth_bidi_test(
    () => getUserDescriptionDescriptor()
              .then(_ => ({descriptor, fake_peripheral, fake_service} = _))
              .then(() => fake_service.remove())
              .then(
                  () => assert_promise_rejects_with_message(
                      descriptor.CALLS(
                          [readValue() |
                           writeValue(new ArrayBuffer(1 /* length */))]),
                      expected, 'Service got removed.')),
    test_desc);
