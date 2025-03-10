// META: title=IndexedDB: IDBKeyRange.includes()
// META: global=window,worker
// META: script=resources/support.js

// Spec: https://w3c.github.io/IndexedDB/#keyrange

'use strict';

test(() => {
  const range = IDBKeyRange.bound(12, 34);
  assert_throws_js(TypeError, () => {
    range.includes();
  }, 'throws if key is not specified');

  assert_throws_dom('DataError', () => {
    range.includes(undefined);
  }, 'throws if key is undefined');
  assert_throws_dom('DataError', () => {
    range.includes(null);
  }, 'throws if key is null');
  assert_throws_dom('DataError', () => {
    range.includes({});
  }, 'throws if key is not valid type');
  assert_throws_dom('DataError', () => {
    range.includes(NaN);
  }, 'throws if key is not valid number');
  assert_throws_dom('DataError', () => {
    range.includes(new Date(NaN));
  }, 'throws if key is not valid date');
  assert_throws_dom('DataError', () => {
    var a = [];
    a[0] = a;
    range.includes(a);
  }, 'throws if key is not valid array');
}, 'IDBKeyRange.includes() with invalid input');

test(() => {
  const closedRange = IDBKeyRange.bound(5, 20);
  assert_true(!!closedRange.includes, 'IDBKeyRange has a .includes');
  assert_true(closedRange.includes(7), 'in range');
  assert_false(closedRange.includes(1), 'below range');
  assert_false(closedRange.includes(42), 'above range');
  assert_true(closedRange.includes(5.01), 'at the lower end of the range');
  assert_true(closedRange.includes(19.99), 'at the upper end of the range');
  assert_false(closedRange.includes(4.99), 'right below range');
  assert_false(closedRange.includes(21.01), 'right above range');

  assert_true(closedRange.includes(5), 'lower boundary');
  assert_true(closedRange.includes(20), 'upper boundary');
}, 'IDBKeyRange.includes() with a closed range');

test(() => {
  const closedRange = IDBKeyRange.bound(5, 20, true, true);
  assert_true(closedRange.includes(7), 'in range');
  assert_false(closedRange.includes(1), 'below range');
  assert_false(closedRange.includes(42), 'above range');
  assert_true(closedRange.includes(5.01), 'at the lower end of the range');
  assert_true(closedRange.includes(19.99), 'at the upper end of the range');
  assert_false(closedRange.includes(4.99), 'right below range');
  assert_false(closedRange.includes(21.01), 'right above range');

  assert_false(closedRange.includes(5), 'lower boundary');
  assert_false(closedRange.includes(20), 'upper boundary');
}, 'IDBKeyRange.includes() with an open range');

test(() => {
  const range = IDBKeyRange.bound(5, 20, true);
  assert_true(range.includes(7), 'in range');
  assert_false(range.includes(1), 'below range');
  assert_false(range.includes(42), 'above range');
  assert_true(range.includes(5.01), 'at the lower end of the range');
  assert_true(range.includes(19.99), 'at the upper end of the range');
  assert_false(range.includes(4.99), 'right below range');
  assert_false(range.includes(21.01), 'right above range');

  assert_false(range.includes(5), 'lower boundary');
  assert_true(range.includes(20), 'upper boundary');
}, 'IDBKeyRange.includes() with a lower-open upper-closed range');

test(() => {
  const range = IDBKeyRange.bound(5, 20, false, true);
  assert_true(range.includes(7), 'in range');
  assert_false(range.includes(1), 'below range');
  assert_false(range.includes(42), 'above range');
  assert_true(range.includes(5.01), 'at the lower end of the range');
  assert_true(range.includes(19.99), 'at the upper end of the range');
  assert_false(range.includes(4.99), 'right below range');
  assert_false(range.includes(21.01), 'right above range');

  assert_true(range.includes(5), 'lower boundary');
  assert_false(range.includes(20), 'upper boundary');
}, 'IDBKeyRange.includes() with a lower-closed upper-open range');

test(() => {
  const onlyRange = IDBKeyRange.only(42);
  assert_true(onlyRange.includes(42), 'in range');
  assert_false(onlyRange.includes(1), 'below range');
  assert_false(onlyRange.includes(9000), 'above range');
  assert_false(onlyRange.includes(41), 'right below range');
  assert_false(onlyRange.includes(43), 'right above range');
}, 'IDBKeyRange.includes() with an only range');

test(() => {
  const range = IDBKeyRange.lowerBound(5);
  assert_false(range.includes(4), 'value before closed lower bound');
  assert_true(range.includes(5), 'value at closed lower bound');
  assert_true(range.includes(6), 'value after closed lower bound');
  assert_true(range.includes(42), 'value way after open lower bound');
}, 'IDBKeyRange.includes() with an closed lower-bounded range');

test(() => {
  const range = IDBKeyRange.lowerBound(5, true);
  assert_false(range.includes(4), 'value before open lower bound');
  assert_false(range.includes(5), 'value at open lower bound');
  assert_true(range.includes(6), 'value after open lower bound');
  assert_true(range.includes(42), 'value way after open lower bound');
}, 'IDBKeyRange.includes() with an open lower-bounded range');

test(() => {
  const range = IDBKeyRange.upperBound(5);
  assert_true(range.includes(-42), 'value way before closed upper bound');
  assert_true(range.includes(4), 'value before closed upper bound');
  assert_true(range.includes(5), 'value at closed upper bound');
  assert_false(range.includes(6), 'value after closed upper bound');
}, 'IDBKeyRange.includes() with an closed upper-bounded range');

test(() => {
  const range = IDBKeyRange.upperBound(5, true);
  assert_true(range.includes(-42), 'value way before closed upper bound');
  assert_true(range.includes(4), 'value before open upper bound');
  assert_false(range.includes(5), 'value at open upper bound');
  assert_false(range.includes(6), 'value after open upper bound');
}, 'IDBKeyRange.includes() with an open upper-bounded range');

test((t) => {
  assert_true(IDBKeyRange.bound(new Date(0), new Date())
                  .includes(new Date(102729600000)));
  assert_false(IDBKeyRange.bound(new Date(0), new Date(1e11))
                   .includes(new Date(1e11 + 1)));

  assert_true(IDBKeyRange.bound('a', 'c').includes('b'));
  assert_false(IDBKeyRange.bound('a', 'c').includes('d'));

  assert_true(IDBKeyRange.bound([], [[], []]).includes([[]]));
  assert_false(IDBKeyRange.bound([], [[]]).includes([[[]]]));
}, 'IDBKeyRange.includes() with non-numeric keys');
