'''
Supporting function for document scanner

cornerPoints(image) - locating the corners of the document in question in an image
findName(string) - extracting file name without file extension to output in a unique folder
perspectiveTransform(image, list) - extract the location of the corner points and set thme as the base coordinates
@author: Jeffrey
'''

from PIL import Image
import numpy as np
import os
import copy
import cv2
import sys, traceback
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

def scaleTarget(corner, shrink_scale):
    try:
        cornerNew = corner.reshape((4,2))
        rect = np.zeros((4,2), dtype = np.float32)
        add = cornerNew.sum(axis = 1)
        rect[0] = cornerNew[np.argmin(add)]
        rect[2] = cornerNew[np.argmax(add)]
        
        diff = np.diff(cornerNew, axis = 1)
        rect[1] = cornerNew[np.argmin(diff)]
        rect[3] = cornerNew[np.argmax(diff)]

        (topLeft, topRight, bottomRight, bottomLeft) = rect
        
        widthA = np.sqrt(((bottomRight[0] - bottomLeft[0]) ** 2) + ((bottomRight[1] - bottomLeft[1]) ** 2))
        widthB = np.sqrt(((topRight[0] - topLeft[0]) ** 2) + ((topRight[1] - topLeft[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.sqrt(((topRight[0] - bottomRight[0]) ** 2) + ((topRight[1] - bottomRight[1]) ** 2))
        heightB = np.sqrt(((topLeft[0] - bottomLeft[0]) ** 2) + ((topLeft[1] - bottomLeft[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))


        scale = shrink_scale
        heightScale = scale * maxHeight
        widthScale = scale * maxWidth
        corner[0][0] = [rect[0][0] + widthScale, rect[0][1] + heightScale]
        corner[1][0] = [rect[1][0] - widthScale, rect[1][1] + heightScale]
        corner[2][0] = [rect[2][0] - widthScale, rect[2][1] - heightScale]
        corner[3][0] = [rect[3][0] + widthScale, rect[3][1] - heightScale]
    except:
        print("BUGBUGUBUG")
        traceback.print_exc(file=sys.stdout)
    return corner

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
            'x2': x + w - 1,
            'y2': y + h - 1,
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
    
def textDetection(imagePath):

    image = cv2.imread(imagePath)
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ret, mask = cv2.threshold(grayscale, 180, 255, cv2.THRESH_BINARY)
    imageFinal = cv2.bitwise_and(grayscale, grayscale, mask = mask)
    ret, newImage = cv2.threshold(imageFinal, 180, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    dilated = cv2.dilate(newImage, kernel, iterations = 9)
    
    _, contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    
    for c in contours:
        [x, y, w, h] = cv2.boundingRect(c)
        if w < 35 and h < 35:
            continue
        cv2.rectangle(image, (x, y), (x + w, y + h), (255, 0, 255), 2)
        
        cv2.imshow('detection result', image)
        cv2.waitKey()
        
    return image;

def polyArea(target):
    x = []
    y = []
    for pos in target:
        x.append(pos[0][0])
        y.append(pos[0][1])
    return 0.5*np.abs(np.dot(x,np.roll(y,1))-np.dot(y,np.roll(x,1)))

def textDetection2(imagePath):
    maxArea = 150
    minArea = 10
    image = cv2.imread(imagePath)
    grayscale = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
    ret, threshold1 = cv2.threshold(grayscale, 0, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    components = cv2.connectedComponentsWithStats(threshold1)
    labels = components[1]
    labelStats = components[2]
    labelAreas = labelStats[:,4]
    
    for comps in range(1, components[0], 1):
        if labelAreas[comps] > maxArea or labelAreas[comps] < minArea:
            labels[labels == comps] = 0
    labels[labels > 0] = 1
    
    se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    dilated = cv2.morphologyEx(labels.astype(np.uint8), cv2.MORPH_DILATE, se)
    
    comp = cv2.connectedComponentsWithStats(dilated)
    
    labels = comp[1]
    labelStats = comp[2]
    
    for compLabel in range(1, comp[0], 1):
        cv2.rectangle(image,(labelStats[compLabel,0],labelStats[compLabel,1]),(labelStats[compLabel,0]+labelStats[compLabel,2],labelStats[compLabel,1]+labelStats[compLabel,3]),(0,0,255),2)
    cv2.imshow('detection result', image)
    cv2.waitKey()
    return image;

def find_if_close(cnt1,cnt2, height, width):
    row1,row2 = cnt1.shape[0],cnt2.shape[0]
    arr_ct1_x = [x[0][0] for x in cnt1]
    arr_ct1_y = [x[0][1] for x in cnt1]
    ct1_x_min_max = [min(arr_ct1_x), max(arr_ct1_x)]
    ct1_y_min_max = [min(arr_ct1_y), max(arr_ct1_y)]
    arr_ct2_x = [x[0][0] for x in cnt2]
    arr_ct2_y = [x[0][1] for x in cnt2]
    ct2_x_min_max = [min(arr_ct2_x), max(arr_ct2_x)]
    ct2_y_min_max = [min(arr_ct2_y), max(arr_ct2_y)]
    for i in range(0,row1,2):
        for j in range(0,row2,2):
            ct1_x, ct2_x, ct1_y, ct2_y = cnt1[i][0][0], cnt2[j][0][0], cnt1[i][0][1], cnt2[j][0][1]
            dist_x = abs(ct1_x-ct2_x)
            dist_y = abs(ct1_y-ct2_y)
            if dist_x / width < 0.015 and dist_y / height < 0.010 :
                return True
            elif ct1_x < ct2_x_min_max[1] and ct1_x > ct2_x_min_max[0] and ct1_y < ct2_y_min_max[1] and ct1_y > ct2_y_min_max[0]:
                return True
            elif ct2_x < ct1_x_min_max[1] and ct2_x > ct1_x_min_max[0] and ct2_y < ct1_y_min_max[1] and ct2_y > ct1_y_min_max[0]:
                return True
            elif i==row1-1 and j==row2-1:
                return False

def combineContours(contours, width, height):
    LENGTH = len(contours)
    status = np.zeros((LENGTH,1))
    combined = False
    for i,cnt1 in enumerate(contours):
        x = i    
        if i != LENGTH-1:
            for j,cnt2 in enumerate(contours[i+1:]):
                x = x+1
                dist = find_if_close(cnt1,cnt2, width, height)
                if dist == True:
                    combined = True
                    val = min(status[i],status[x])
                    status[x] = status[i] = val
                else:
                    if status[x]==status[i]:
                        status[x] = i+1

    unified = []
    maximum = int(status.max())+1
    for i in range(maximum):
        pos = np.where(status==i)[0]
        if pos.size != 0:
            cont = np.vstack(contours[i] for i in pos)
            hull = cv2.convexHull(cont)
            unified.append(hull)
    if combined:
        unified = combineContours(unified, width, height)
    return unified

def saveImage(image, prefix):
    tmp_folder = "tmp" + str(prefix)
    if not os.path.exists(tmp_folder):
        os.makedirs(tmp_folder)
    tmp_folder = tmp_folder + os.sep + "rect_outline.jpg"
    cv2.imwrite(tmp_folder, image)
    return tmp_folder
    
def textDetection3(image, width, height):
    image = image.convert('RGB') 
    image = np.array(image) 
    image2 = copy.deepcopy(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # cv2.imshow('gray',gray)
    # cv2.waitKey(0)
    ret,thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    # cv2.imshow('second', thresh)
    # cv2.waitKey(0)
    kernel = np.ones((5,100), np.uint8)
    img_dilation = cv2.dilate(thresh, kernel, iterations=1)
    # cv2.imshow('dilated', img_dilation)
    # cv2.waitKey(0)
    im2, ctrs, _ = cv2.findContours(img_dilation.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    sorted_ctrs = sorted(ctrs, key=lambda ctr: cv2.boundingRect(ctr)[0])
    sorted_ctrs = combineContours(sorted_ctrs, width, height)
    images = []
    for i, ctr in enumerate(sorted_ctrs):
        x, y, w, h = cv2.boundingRect(ctr)
        roi = image[y:y+h, x:x+w]
        images.append({'roi': roi, 'center': y, 'width': w})
        # cv2.imshow('segment no:'+str(i), roi)
        cv2.rectangle(image2, (x,y), (x + w, y + h), (90, 0, 255), 2)
        # cv2.waitKey(0)
    images.sort(key=lambda datum: (datum['center']))
    # cv2.imshow('marked areas', image)
    # cv2.waitKey(0)
    
    return images, image2;
    