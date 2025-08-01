'use strict';
const test_desc = 'Calls to FUNCTION_NAME should return the same object.';
let characteristic;

bluetooth_bidi_test(
    () => getMeasurementIntervalCharacteristic()
              .then(_ => ({characteristic} = _))
              .then(() => Promise.all([
                characteristic.CALLS(
                    [getDescriptor(user_description.alias) |
                     getDescriptors(user_description.alias)]),
                characteristic.FUNCTION_NAME(user_description.name),
                characteristic.FUNCTION_NAME(user_description.uuid)
              ]))
              .then(descriptors_arrays => {
                assert_true(descriptors_arrays.length > 0)

                // Convert to arrays if necessary.
                for (let i = 0; i < descriptors_arrays.length; i++) {
                  descriptors_arrays[i] = [].concat(descriptors_arrays[i]);
                }

                for (let i = 1; i < descriptors_arrays.length; i++) {
                  assert_equals(
                      descriptors_arrays[0].length,
                      descriptors_arrays[i].length);
                }

                let base_set = new Set(descriptors_arrays[0]);
                for (let descriptors of descriptors_arrays) {
                  descriptors.forEach(
                      descriptor => assert_true(base_set.has(descriptor)));
                }
              }),
    test_desc);
