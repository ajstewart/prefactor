import numpy as np
import pyfits
import os,sys
import glob
#from pythoncodes.maths import *
import argparse
import scipy
from scipy.optimize import leastsq

def model_gaussian(t, coeffs):
    return coeffs[0] + coeffs[1] * np.exp( - ((t-coeffs[2])**2.0/(2*coeffs[3]**2)))

def residuals_gaussian(coeffs, y, t):
    return y - model_gaussian(t, coeffs)

def fit_gaussian_histogram(pixelvals,plotting):
 
    fitnumbers,cellsizes = np.histogram(pixelvals,100)
    sigmaguess = np.std(pixelvals)/(abs(cellsizes[1]-cellsizes[0]))
    x0 = [0.0,max(fitnumbers),np.where(fitnumbers==max(fitnumbers))[0][0],sigmaguess] #Offset amp, amp, x-offset, sigma
    t = np.arange(len(fitnumbers))
    x, flag = scipy.optimize.leastsq(residuals_gaussian, x0, args=(fitnumbers, t))
 
    if plotting == 'y':
        pylab.plot(fitnumbers)
        pylab.plot(t,fitnumbers,t,model_gaussian(t,x))
        pylab.show()
        pylab.close()
        pylab.cla()
 
    #print 'Sigma is %s'%(x[3]*abs(cellsizes[1]-cellsizes[0]))
     
    return (x[3]*abs(cellsizes[1]-cellsizes[0]))

def removenoise(noisepix):
 
    noisepix = noisepix.flatten()
 
    noiseconverge = 0
 
    while noiseconverge == 0:
        #print 'searching'
        currentnoise = fit_gaussian_histogram(noisepix,'n')
        noisepix.sort()
        thresholdupp = noisepix[int(len(noisepix)/2)] + 5*currentnoise
        thresholdlow = noisepix[int(len(noisepix)/2)] - 5*currentnoise
        noisepix = np.array(filter(lambda x: x<thresholdupp,noisepix))
        noisepix = np.array(filter(lambda x: x>thresholdlow,noisepix))
        rms = fit_gaussian_histogram(noisepix,'n')
        #print currentnoise,rms
        if rms >= currentnoise*0.90:
            noiseconverge = 1
        else:
            orignoise = rms
 
    return noisepix
 

def concatimages_new(images,outimage,ignorenoise=False):

    infodict = {}
    image = images[0]
    f = pyfits.open(image)    
    if (f[0].header['NAXIS3'] >1 or  f[0].header['BZERO']>0. or f[0].header['BSCALE']!=1.):
        print "Image",image,"has more than two dimensions, or sucks in another way!"
        sys.exit(1)
    if 'BMAJ' in f[0].header:
        bmaj = f[0].header['BMAJ']
        bmin = f[0].header['BMIN']
    else:
        bmaj = 1.
        bmin = 1.
    cdelt1 = f[0].header['CDELT1']
    cdelt2 = f[0].header['CDELT2']
    freq = f[0].header['CRVAL3']
    crval1 = f[0].header['CRVAL1']
    crval2 = f[0].header['CRVAL2']
    naxis = f[0].header['NAXIS']
    naxis1 = f[0].header['NAXIS1']
    naxis2 = f[0].header['NAXIS2']
    crpix1 = f[0].header['CRPIX1']
    crpix2 = f[0].header['CRPIX2']

    print 'working on image %s at %.2f MHz'%(image,freq/1e6)
    if not ignorenoise:
        noisearray = f[0].data.flatten()
        noisearray = np.random.permutation(noisearray)[:100000]
        noisepix = np.array(filter(lambda x: abs(x) > 10E-8,noisearray))
        noisepix = removenoise(noisepix)
        noise = fit_gaussian_histogram(noisepix,'n')
    else:
        noise = 1.
    f.close()
    infodict[image]  = bmaj,bmin,naxis1,naxis2,crpix1,crpix2,freq,noise
    minImage = image

    for image in images[1:]:
        f = pyfits.open(image)
        if (f[0].header['NAXIS3'] >1 or  f[0].header['BZERO']>0. or f[0].header['BSCALE']!=1.):
            print "Image",image,"has more than two dimensions, or sucks in another way!"
            sys.exit(1)
        if (cdelt1 != f[0].header['CDELT1'] or cdelt2 != f[0].header['CDELT2'] or naxis != f[0].header['NAXIS'] or
            crval1 != f[0].header['CRVAL1'] or crval2 != f[0].header['CRVAL2']):
            print  "Image",image,"does not match reference!"
            print cdelt1, f[0].header['CDELT1'], cdelt2, f[0].header['CDELT2'], crval1, f[0].header['CRVAL1'], crval2, f[0].header['CRVAL2'], naxis, f[0].header['NAXIS']
            sys.exit(1)
        if 'BMAJ' in f[0].header:
            bmaj = f[0].header['BMAJ']
            bmin = f[0].header['BMIN']
        else:
            bmaj = 1.
            bmin = 1.
        freq = f[0].header['CRVAL3']
        naxis1 = f[0].header['NAXIS1']
        naxis2 = f[0].header['NAXIS2']
        crpix1 = f[0].header['CRPIX1']
        crpix2 = f[0].header['CRPIX2']
 
        print 'working on image %s at %.2f MHz'%(image,freq/1e6)

        if not ignorenoise:
            noisearray = f[0].data.flatten()
            noisearray = np.random.permutation(noisearray)[:100000]
            noisepix = np.array(filter(lambda x: abs(x) > 10E-8,noisearray))
            noisepix = removenoise(noisepix)
            #noisepix = np.array(filter(lambda x: abs(x)<0.5,noisepix))
            noise = fit_gaussian_histogram(noisepix,'n')
        else:
            noise = 1.
        f.close()
        infodict[image]  = bmaj,bmin,naxis1,naxis2,crpix1,crpix2,freq,noise
        if naxis1 < infodict[minImage][2]:
            minImage = image

    print "Smallest Image:",minImage," print:",infodict[minImage]
    concatshape = (infodict[minImage][3],infodict[minImage][2])
    concatpix = np.zeros(concatshape,dtype='>f4')
    weightsum = 0.0
    sumfreq = 0.0
    for image in images:
        f = pyfits.open(image)
        weight = 1/infodict[image][7]**2.0
        print "Adding image: %s with weight: %.1f"%(image,weight)
        startax1 = int(f[0].header['CRPIX1']-infodict[minImage][4])
        startax2 = int(f[0].header['CRPIX2']-infodict[minImage][5])
        endax1 = int(startax1+infodict[minImage][2])
        endax2 = int(startax2+infodict[minImage][3])
        concatpix += f[0].data[0,0,startax2:endax2,startax1:endax1]*weight
        weightsum += weight
        sumfreq += f[0].header['CRVAL3']
    concatpix /= weightsum
    if naxis==3:
        concatpix = np.reshape(concatpix,(1,concatshape[0],concatshape[1]))
    elif naxis==4:
        concatpix = np.reshape(concatpix,(1,1,concatshape[0],concatshape[1]))
    f = pyfits.open(minImage)
    outfile=pyfits.PrimaryHDU(data=concatpix)
    for key in ['SIMPLE', 'BITPIX', 'NAXIS', 'NAXIS1', 'NAXIS2', 'NAXIS3', 'NAXIS4', 'EXTEND', 'BSCALE', 'BZERO', 'BUNIT', 'BMAJ', 'BMIN', 'BPA', 'EQUINOX', 'BTYPE', 'CTYPE1', 'CRPIX1', 'CRVAL1', 'CDELT1', 'CUNIT1', 'CTYPE2', 'CRPIX2', 'CRVAL2', 'CDELT2', 'CUNIT2', 'CTYPE3', 'CRPIX3', 'CRVAL3', 'CDELT3', 'CUNIT3', 'CTYPE4', 'CRPIX4', 'CRVAL4', 'CDELT4', 'CUNIT4', 'SPECSYS', 'DATE-OBS', 'WSCDATAC', 'WSCWEIGH', 'WSCFIELD', 'WSCGAIN', 'WSCGKRNL', 'WSCIMGWG', 'WSCMAJOR', 'WSCMGAIN', 'WSCMINOR', 'WSCNEGCM', 'WSCNEGST', 'WSCNITER', 'WSCNWLAY', 'WSCTHRES']:
        if key in f[0].header:
            outfile.header[key] = f[0].header[key]
    outfile.header['CRVAL3'] = sumfreq/len(images)
    outfile.writeto(outimage)
    f.close()
    return True

# in case I want to call it as a pythonplugin...
def main(images,outimage):
    return concatimages_new(images,outimage)


if __name__ == '__main__':
    descriptiontext = "Stack images generated by the Initial-Subtract pipeline.\n (Images need to be in fits format, have the same reference position, same step-size, and same axes.)\n"

    parser = argparse.ArgumentParser(description=descriptiontext)
    parser.add_argument('im_file_pattern', help='Glob-able filename-pattern of input images. (Usually needs to be put in quotation marks: \" or \')')
    parser.add_argument('outimage', help='Name of output image to generate.')
    parser.add_argument('--ignorenoise','-i', action="store_true", dest='ignorenoise',
                      help='Ignore the noise in the images, give all images the same weight.')

    args = parser.parse_args()
    imlist = glob.glob(args.im_file_pattern)
    concatimages_new(imlist, args.outimage, args.ignorenoise)
