'''
Supporting function for document scanner

cornerPoints(image) - locating the corners of the document in question in an image
findName(string) - extracting file name without file extension to output in a unique folder
perspectiveTransform(image, list) - extract the location of the corner points and set thme as the base coordinates
@author: Jeffrey
'''

from PIL import Image
import numpy as np
import cv2
from imutils.perspective import order_points

def cornerPoints(corner):
    corner = corner.reshape((4,2))
    rect = np.zeros((4,2), dtype = np.float32)
    
    add = corner.sum(axis = 1)
    rect[0] = corner[np.argmin(add)]
    rect[2] = corner[np.argmax(add)]
    
    diff = np.diff(corner, axis = 1)
    rect[1] = corner[np.argmin(diff)]
    rect[3] = corner[np.argmax(diff)]
    
    return rect

def findName(name):
    indType = name.find('.')
    nameOnly = name[0:indType] + '/'
    return nameOnly

def perspectiveTransform(image, points):
    rect = order_points(points)
    (topLeft, topRight, bottomRight, bottomLeft) = rect
    
    widthA = np.sqrt(((bottomRight[0] - bottomLeft[0]) ** 2) + ((bottomRight[1] - bottomLeft[1]) ** 2))
    widthB = np.sqrt(((topRight[0] - topLeft[0]) ** 2) + ((topRight[1] - topLeft[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    heightA = np.sqrt(((topRight[0] - bottomRight[0]) ** 2) + ((topRight[1] - bottomRight[1]) ** 2))
    heightB = np.sqrt(((topLeft[0] - bottomLeft[0]) ** 2) + ((topLeft[1] - bottomLeft[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    
    destinationPoints = np.array([
        [0,0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]],
        dtype = "float32")
    
    M = cv2.getPerspectiveTransform(rect,destinationPoints)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    
    return warped
    
def downscale_image(image, max_dim=2048):
    a, b = image.size
    if max(a, b) <= max_dim:
        return 1.0, image
    scale = 1.0 * max_dim / max(a, b)
    newImage = image.resize((int(a * scale), int(b * scale)), Image.ANTIALIAS)
    return scale, newImage

def findBorder(contours, arr):
    borders = []
    area = arr.shape[0] * arr.shape[1]
    for i, c in enumerate(contours):
        x, y, w, h = cv2.boundingRect(c)
        if w * h > 0.5 * area:
            borders.append((i, x, y, x + w - 1, y + h - 1))
    return borders

def removeBorder(contour, arr):
    conImage = np.zeros(arr.shape)
    rem = cv2.minAreaRect(contour)
    degrees = rem[2]
    if min(degrees % 90, 90 - (degrees % 90)) <= 10.0:
        box = cv2.boxPoints(rem)
        box = np.int0(box)
        cv2.drawContours(conImage, [box], 0, 255, -1)
        cv2.drawContours(conImage, [box], 0, 0, 4)
    else:
        x1, y1, x2, y2 = cv2.boundingRect(contour)
        cv2.rectangle(conImage, (x1, y1), (x2, y2), 255, -1)
        cv2.rectangle(conImage, (x1, y1), (x2, y2), 0, 4)
    return np.minimum(conImage, arr)

def dilate(arr, N, iterations):
    kernel = np.zeros((N, N), dtype=np.uint8)
    kernel[(N-1)//2,:] = 1
    dilateImage = cv2.dilate(arr/255, kernel, iterations = iterations)
    kernel = np.zeros((N, N), dtype=np.uint8)
    kernel[:,(N-1)//2] = 1
    dilateImage = cv2.dilate(dilateImage, kernel, iterations = iterations)
    return dilateImage

def findComponents(edges, maxComps=16):
    count = 21
    dilation = 5
    n = 1
    while count > 16:
        n += 1
        dilateImage = dilate(edges, N = 3, iterations = n)
        dilateImage = np.uint8(dilateImage)
        _, contours, _ = cv2.findContours(dilateImage, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        count = len(contours)
    print(count)
    return contours

def contourAssist(contours, arr):
    cInfo = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        cImage = np.zeros(arr.shape)
        cv2.drawContours(cImage, [c], 0, 255, -1)
        cInfo.append({
            'x1': x,
            'y1': y,
            'x2': x + w -1,
            'y2': y + h -1,
            'sum': np.sum(arr * (cImage > 0))/255
        })
    return cInfo

def cropArea(crop):
    x1, y1, x2, y2, = crop
    return max(0, x2 - x1) * max(0, y2 - y1)

def cropByUnion(crop1, crop2):
    x11, y11, x21, y21 = crop1
    x12, y12, x22, y22 = crop2
    return min(x11, x12), min(y11, y12), max(x21, x22), max(y21, y22)

def cropByIntersect(crop1, crop2):
    x11, y11, x21, y21 = crop1
    x12, y12, x22, y22 = crop2
    return max(x11, x12), max(y11, y12), min(x21, x22), min(y21, y22)

def findOptimalComponents(contours, edges):
    cInfo = contourAssist(contours, edges)
    cInfo.sort(key=lambda x: -x['sum'])
    total = np.sum(edges) / 255
    area = edges.shape[0] * edges.shape[1]
    c = cInfo[0]
    del cInfo[0]
    thisCrop = c['x1'], c['y1'], c['x2'], c['y2']
    crop = thisCrop
    coveredSum = c['sum']
    
    while coveredSum < total:
        changed = False
        recall = 1.0 * coveredSum / total
        prec = 1 - 1.0 * cropArea(crop) / area
        f1 = 2 * (prec * recall / (prec + recall))
        for i, c in enumerate(cInfo):
            currCrop = c['x1'], c['y1'], c['x2'], c['y2']
            newCrop = cropByUnion(crop, currCrop)
            newSum = coveredSum + c['sum']
            newRecall = 1.0 * newSum / total
            newPrec = 1 - 1.0 * cropArea(newCrop) / area
            newF1 = 2 * newPrec * newRecall / (newPrec + newRecall)
            
            remainFraction = c['sum'] / (total - coveredSum)
            newAreaFraction = 1.0 * cropArea(newCrop) / cropArea(crop) - 1
            if newF1 > f1 or (remainFraction > 0.025 and newAreaFraction < 0.15):
                crop = newCrop
                coveredSum = newSum
                del cInfo[i]
                changed = True
                break
        if not changed:
            break
    return crop

def padCrop(crop, contours, edges, borderContour, padPx=15):
    bx1, by1, bx2, by2 = 0, 0, edges.shape[0], edges.shape[1]
    if borderContour is not None and len(borderContour) > 0:
        c = contourAssist([borderContour], edges)[0]
        bx1, by1, bx2, by2 = c['x1'] + 5, c['y1'] + 5, c['x2'] - 5, c['y2'] -5
        
    def cropByBorder(crop):
        x1, y1, x2, y2 = crop
        x1 = max(x1 - padPx, bx1)
        y1 = max(y1 - padPx, by1)
        x2 = max(x2 + padPx, bx2)
        y2 = max(y2 + padPx, by2)
        return crop
    
    crop = cropByBorder(crop)
    cInfo = contourAssist(contours, edges)
    changed = False
    for c in cInfo:
        currCrop = c['x1'], c['y1'], c['x2'], c['y2']
        currArea = cropArea(currCrop)
        intArea = cropArea(cropByIntersect(crop, currCrop))
        newCrop = cropByBorder(cropByUnion(crop, currCrop))
        if 0 < intArea < currArea and crop != newCrop:
            changed = True
            crop = newCrop
    if changed:
        return padCrop(crop, contours, edges, borderContour, padPx)
    else:
        return crop