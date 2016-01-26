from __future__ import division, print_function
import os.path
import shutil
import tempfile
import numpy as np
import h5py
import out_of_core_fft

oneGB_complex = 64 * 1024**2
oneMB_complex = 64 * 1024


def test_big_transpose():
    print()
    with out_of_core_fft._TemporaryDirectory() as temp_dir:
        # Write a test file of 1-d data to be reinterpreted as 2-d and transposed
        np.random.seed(1234)
        N = oneGB_complex * 2
        N_creation = min(16*1024**2, N)
        print("\tCreating file with test data, N={0}".format(N))
        with h5py.File(os.path.join(temp_dir, 'test_in.h5'), 'w') as f:
            x = f.create_dataset('x', shape=(N,), dtype=complex)
            for k in range(0, N, N_creation):
                size = min(N-k, N_creation)
                x[k:k+size] = np.random.random(size) + 1j*np.random.random(size)
        print("\t\tFinished creating file with test data")

        # Now transpose it to file
        print("\tPerforming first transpose")
        with h5py.File(os.path.join(temp_dir, 'test_in.h5'), 'r') as f:
            x = f['x']
            R2, C2 = N//1024, 1024
            f2, d = out_of_core_fft.transpose(x, os.path.join(temp_dir, 'test_transpose.h5'), 'x', R2=R2, C2=C2)
            f2.close()
        print("\t\tFinished performing first transpose")

        # Transpose it back, and check for equality
        print("\tPerforming second transpose")
        with h5py.File(os.path.join(temp_dir, 'test_transpose.h5'), 'r') as f:
            x = f['x']
            f2, d = out_of_core_fft.transpose(x, os.path.join(temp_dir, 'test_transpose2.h5'), 'x')
            try:
                assert np.all([np.array_equal(x[c2a:c2b, r2a:r2b].T, d[r2a:r2b, c2a:c2b])
                               for r2a in range(0, R2, min(R2, C2)) for r2b in [min(R2, r2a+min(R2, C2))]
                               for c2a in range(0, C2, min(R2, C2)) for c2b in []])
            finally:
                f2.close()
        print("\t\tFinished performing second transpose")


def test_small_transpose():
    """This should do the same as above, but with a smaller data set.  By setting the cache size even smaller, I still
    test the actual on-disk transpose function.  As much as anything, this is here to provide a template for other
    tests.
    """
    print()
    with out_of_core_fft._TemporaryDirectory() as temp_dir:
        # Write a test file of 1-d data to be reinterpreted as 2-d and transposed
        np.random.seed(1234)
        N = oneMB_complex * 2
        print("\tCreating file with test data, N={0}".format(N))
        with h5py.File(os.path.join(temp_dir, 'test_in.h5'), 'w') as f:
            f.create_dataset('x', data=(np.random.random(N) + 1j*np.random.random(N)))
        print("\t\tFinished creating file with test data")

        # Now transpose it to file
        print("\tPerforming first transpose")
        with h5py.File(os.path.join(temp_dir, 'test_in.h5'), 'r') as f:
            x = f['x']
            R2, C2 = N//32, 32
            f2, d = out_of_core_fft.transpose(x, os.path.join(temp_dir, 'test_transpose.h5'), 'x', R2=R2, C2=C2,
                                              chunk_cache_mem_size=N//2)
            f2.close()
        print("\t\tFinished performing first transpose")

        # Transpose it back, and check for equality
        print("\tPerforming second transpose")
        with h5py.File(os.path.join(temp_dir, 'test_transpose.h5'), 'r') as f:
            x = f['x']
            f2, d = out_of_core_fft.transpose(x, os.path.join(temp_dir, 'test_transpose2.h5'), 'x',
                                              chunk_cache_mem_size=N//2)
            try:
                assert np.all([np.array_equal(x[c2a:c2b, r2a:r2b].T, d[r2a:r2b, c2a:c2b])
                               for r2a in range(0, R2, min(R2, C2)) for r2b in [min(R2, r2a+min(R2, C2))]
                               for c2a in range(0, C2, min(R2, C2)) for c2b in []])
            finally:
                f2.close()
        print("\t\tFinished performing second transpose")


def test_small_ifft():
    print()
    with out_of_core_fft._TemporaryDirectory() as temp_dir:
        # Write a test file
        np.random.seed(1234)
        N = oneMB_complex * 4
        fname_in = os.path.join(temp_dir, 'test_in.h5')
        fname_out = os.path.join(temp_dir, 'test_out.h5')
        print("\tCreating file with test data, N={0}".format(N))
        with h5py.File(fname_in, 'w') as f:
            f.create_dataset('X', data=(np.random.random(N) + 1j*np.random.random(N)))
        print("\t\tFinished creating file with test data")

        # FFT it
        print("\tPerforming out-of-core FFT")
        out_of_core_fft.ifft(fname_in, 'X', fname_out, 'x', mem_limit=1024**2)
        print("\t\tFinished performing out-of-core FFT")

        # Compare to in-core FFT
        with h5py.File(fname_in, 'r') as f_in, h5py.File(fname_out, 'r') as f_out:
            assert np.allclose(f_in['X'].shape[0]*np.fft.ifft(f_in['X']), f_out['x'])


def test_small_fft():
    print()
    with out_of_core_fft._TemporaryDirectory() as temp_dir:
        # Write a test file
        np.random.seed(1234)
        N = oneMB_complex * 4
        fname_in = os.path.join(temp_dir, 'test_in.h5')
        fname_out = os.path.join(temp_dir, 'test_out.h5')
        print("\tCreating file with test data, N={0}".format(N))
        with h5py.File(fname_in, 'w') as f:
            f.create_dataset('x', data=(np.random.random(N) + 1j*np.random.random(N)))
        print("\t\tFinished creating file with test data")

        # FFT it
        print("\tPerforming out-of-core FFT")
        out_of_core_fft.fft(fname_in, 'x', fname_out, 'X', mem_limit=1024**2)
        print("\t\tFinished performing out-of-core FFT")

        # Compare to in-core FFT
        with h5py.File(fname_in, 'r') as f_in, h5py.File(fname_out, 'r') as f_out:
            assert np.allclose(np.fft.fft(f_in['x']), f_out['X'])



