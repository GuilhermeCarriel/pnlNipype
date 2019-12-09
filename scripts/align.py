#!/usr/bin/env python


from plumbum import cli
import numpy as np
from numpy import diag, linalg, vstack, hstack, array

from conversion.bval_bvec_io import bvec_rotate

precision= 17


def get_spcdir_new(hdr_in):

    spcdir_orig= hdr_in.get_best_affine()[0:3,0:3].T

    sizes = diag(hdr_in['pixdim'][1:4])
    spcON = linalg.inv(sizes) @ spcdir_orig
    spcNN = np.zeros([3, 3])

    for i in range(0, 3):
        mi = np.argmax(abs(spcON[i, :]))
        spcNN[i, mi] = np.sign(spcON[i, mi])

    R = spcNN @ linalg.inv(spcON)

    spcdir_new = spcNN.T @ sizes

    return (spcdir_new, R)


def axis_align_dwi(hdr_in, bvec_file, bval_file, out_prefix):

    spcdir_new, R= get_spcdir_new(hdr_in)

    bvec_rotate(bvec_file, out_prefix+'.bvec', rot_matrix=R)

    # rename the bval file
    bval_file.copy(out_prefix+'.bval')

    return spcdir_new

def axis_align_3d(hdr_in):

    spcdir_new, _ = get_spcdir_new(hdr_in)

    return spcdir_new


def update_hdr(hdr_in, spcdir_new, offset_new):

    hdr_out= hdr_in.copy()

    xfrm= vstack((hstack((spcdir_new, array(offset_new))), [0., 0., 0., 1]))

    hdr_out.set_sform(xfrm, code= 'aligned')
    hdr_out.set_qform(xfrm, code= 'aligned')
    
    return hdr_out

def work_flow(img_file, out_prefix, axisAlign=False, center=False, bval_file=None, bvec_file=None):

    from plumbum import local
    from util import load_nifti, save_nifti
    from align import axis_align_3d, update_hdr, axis_align_dwi
    from numpy import matrix

    img_file = local.path(img_file)
    bval_file= local.path(bval_file)
    bvec_file= local.path(bvec_file)

    if img_file.endswith('.nii') or img_file.endswith('.nii.gz'):
        mri = load_nifti(img_file._path)
    else:
        print('Invalid image format, accepts nifti only')
        exit(1)

    hdr = mri.header
    dim = hdr['dim'][0]

    if dim == 4:
        if not bvec_file and not bval_file:
            print('bvec and bvals files not specified, exiting ...')
            exit(1)

    elif dim == 3:
        spcdir_new = axis_align_3d(hdr)

    else:
        print('Invalid image dimension, has to be either 3 or 4')

    offset_orig = matrix(hdr.get_best_affine()[0:3, 3]).T
    spcdir_orig = hdr.get_best_affine()[0:3, 0:3]

    if axisAlign and not center:
        # pass spcdir_new and offset_orig

        if not out_prefix:
            out_prefix = img_file.split('.')[0] + '-ax'  # a clever way to get prefix including path

        if dim == 4:
            spcdir_new = axis_align_dwi(hdr, bvec_file, bval_file, out_prefix)

        hdr_out = update_hdr(hdr, spcdir_new, offset_orig)


    elif not axisAlign and center:
        # pass spcdir_orig and offset_new

        if not out_prefix:
            out_prefix = img_file.split('.')[0] + '-ce'  # a clever way to get prefix including path

        offset_new = -spcdir_orig @ matrix((hdr['dim'][1:4] - 1) / 2).T
        hdr_out = update_hdr(hdr, spcdir_orig, offset_new)

        # rename the bval file
        bval_file.copy(out_prefix + '.bval')
        # rename the bvec file
        bvec_file.copy(out_prefix + '.bvec')


    else:  # axisAlign and center:
        # pass spcdir_new and offset_new

        if not out_prefix:
            out_prefix = img_file.split('.')[0] + '-xc'  # a clever way to get prefix including path

        if dim == 4:
            spcdir_new = axis_align_dwi(hdr, bvec_file, bval_file, out_prefix)

        offset_new = -spcdir_new @ matrix((hdr['dim'][1:4] - 1) / 2).T
        hdr_out = update_hdr(hdr, spcdir_new, offset_new)

    # write out the modified image
    save_nifti(out_prefix + '.nii.gz', mri.get_data(), hdr_out.get_best_affine(), hdr_out)

    if dim == 3:
        return out_prefix + '.nii.gz'
    else:
        return (out_prefix + '.nii.gz', out_prefix + '.bval', out_prefix + '.bvec')



class Xalign(cli.Application):
    '''Axis alignment and centering of a 3D/4D NIFTI image'''

    img_file = cli.SwitchAttr(
        ['-i', '--input'],
        cli.ExistingFile,
        help='a 3d or 4d nifti image',
        mandatory=True)

    bvec_file= cli.SwitchAttr(
        ['--bvecs'],
        cli.ExistingFile,
        help='bvec file',
        mandatory=False)

    bval_file= cli.SwitchAttr(
        ['--bvals'],
        cli.ExistingFile,
        help='bval file',
        mandatory=False)

    out_prefix = cli.SwitchAttr(
        ['-o', '--out_prefix'],
        help='prefix for naming dwi, bval, and bvec files',
        mandatory=False)

    axisAlign = cli.Flag(
        ['--axisAlign'],
        help='turn on for axis alignment',
        mandatory=False,
        default= False)

    center = cli.Flag(
        ['--center'],
        help='turn on for centering',
        mandatory=False,
        default= False)


    def main(self):

        work_flow(self.img_file, self.out_prefix, self.axisAlign, self.center, self.bval_file, self.bvec_file)


if __name__ == '__main__':
    Xalign.run()
