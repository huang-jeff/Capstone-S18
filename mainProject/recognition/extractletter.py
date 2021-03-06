from xml.dom import minidom
from svg.path import Path, Line, Arc, CubicBezier, QuadraticBezier
from svg.path import parse_path
from PIL import Image, ImageFilter, ExifTags
import cv2
import os
import random
import shutil
import pickle
import classify
import classify
from subprocess import Popen, PIPE, STDOUT, call
import argparse
import sys
import numpy as np
from scipy.spatial import distance
import math, cmath
import re
from io import BytesIO
import copy

def fixLetters(words):
    for w in words:
        if 'letters' not in w:
            w['letters'] = [w]

def fixWordOrder(words):
    for w in words:
        [min_x, min_y], [max_x, max_y] = w['points'].min(axis=0), w['points'].max(axis=0)
        w['center'] = (min_x + max_x) / 2
    words.sort(key=lambda datum: (datum['center']))

def combineWords(groups, width, threshold):
    # combining in loop
    to_remove = []
    groups = copy.deepcopy(groups)
    grouped = False
    groups_new = groups
    for n, p in enumerate(groups):
        n1 = n + 1
        for p1 in groups_new[n1:]:
            pts = p['points']
            pts2 = p1['points']
            if len(pts) > 3000:
                pts = pts[0::int(len(pts) / 3000)]
            if len(pts2) > 3000:
                pts2 = pts2[0::int(len(pts2) / 3000)]
            dist_arr = distance.cdist(pts, pts2, 'euclidean')
            dist = dist_arr.min()
            if dist < width / threshold:
                print("Combined group",n)
                if 'letters' in p:
                    p['letters'].append(copy.deepcopy(p1))
                else:
                    p['letters'] = [copy.deepcopy(p), copy.deepcopy(p1)]
                p['points'] = np.concatenate((p['points'], pts2))
                p['paths']  += p1['paths']
                grouped = True
                to_remove.append(p1)
            n1 += 1
        groups_new = []
        for i in groups:
            add = True
            for j in to_remove:
                if i['paths'] == j['paths']:
                    add = False
            if add:
                groups_new.append(i)
    groups = groups_new
    if grouped:
        return combineWords(groups, width, threshold)
    else:
        return groups

def combineGroups(groups, width, threshold):
    # combining in loop
    to_remove = []
    groups = copy.deepcopy(groups)
    grouped = False
    groups_new = []
    for n, p in enumerate(groups):
        n1 = n + 1
        for p1 in groups[n1:]:
            pts = copy.deepcopy(p['points'])
            pts2 = copy.deepcopy(p1['points'])
            if len(pts) > 3000:
                pts = pts[0::int(len(pts) / 3000)]
            if len(pts2) > 3000:
                pts2 = pts2[0::int(len(pts2) / 3000)]
            dist_arr = distance.cdist(pts, pts2, 'euclidean')
            dist = dist_arr.min()
            if dist < width / threshold:
                print("Combined group",n)
                p['points'] = np.concatenate((p['points'], p1['points']))
                p['paths']  += p1['paths']
                grouped = True
                to_remove.append(n1)
            n1 += 1
    for i in range(len(groups)):
        if i not in to_remove:
            groups_new.append(groups[i])
    groups = groups_new
    if grouped:
        return combineGroups(groups, width, threshold)
    else:
        return groups

def formBoundaries(groups, image, scale, width, height, path, image2):
    scalar_x = 0.01 * width * scale
    scalar_y = 0.06 * height
    centers = []
    for ind, i in enumerate(groups):
        if 'letters' in i:
            for let in i['letters']:
                ar = np.asarray(let['points'])
                [min_x, min_y], [max_x, max_y] = ar.min(axis=0), ar.max(axis=0)
                min_x, max_y, max_x, min_y = max(int(round(min_x * scale - scalar_x)),0) , min(int(round((height - min_y * scale ) + scalar_y)), height), min(int(round(max_x * scale + scalar_x)), width), max(int(round((height - max_y * scale) - scalar_y)), 0)
                roi = image[min_y:max_y, min_x:max_x]
                centers.append({'center': (min_x + max_x) / 2, 'points': [min_x, max_y, max_x, min_y], 'roi': roi})
                cv2.rectangle(image2, (min_x,min_y), (max_x, max_y), (90, 0, 255), 2)
                # cv2.imshow('segment no:', roi)
                # cv2.waitKey(0)
        else:
            ar = np.asarray(i['points'])
            [min_x, min_y], [max_x, max_y] = ar.min(axis=0), ar.max(axis=0)
            min_x, max_y, max_x, min_y = max(int(round(min_x * scale - scalar_x)),0) , min(int(round((height - min_y * scale ) + scalar_y)), height), min(int(round(max_x * scale + scalar_x)), width), max(int(round((height - max_y * scale) - scalar_y)), 0)
            roi = image[min_y:max_y, min_x:max_x]
            centers.append({'center': (min_x + max_x) / 2, 'points': [min_x, max_y, max_x, min_y], 'roi': roi})
            cv2.rectangle(image2, (min_x,min_y), (max_x, max_y), (90, 0, 255), 2)
    centers.sort(key=lambda datum: (datum['center']))
    for ind, res in enumerate(centers):
        cv2.imwrite(path + os.sep + str(ind) +  ".jpg", res['roi'])


def main(svg_path, model, mapping):
    #parser = argparse.ArgumentParser()
    #args = parser.parse_args()

    doc = minidom.parse(svg_path + os.sep + 'output.svg')  # parseString also exists
    path_strings = [path.getAttribute('d') for path
                    in doc.getElementsByTagName('path')]
    height = float([path.getAttribute('height') for path in doc.getElementsByTagName('svg')][0])
    width = float([path.getAttribute('width') for path in doc.getElementsByTagName('svg')][0])
    scale_raw = [path.getAttribute('transform') for path
                    in doc.getElementsByTagName('g')]
    scale = 1
    try:
        for maybe in scale_raw:
            if 'scale' in maybe:
                scale = float(re.sub(r's.*,', '', maybe).replace(')',''))
                height /= scale
                break
    except:
        print("No scale present")

    def dist_f(x,y):   
        return np.sqrt(np.sum((x-y)**2))
    points = None
    ends = []
    groups = None
    for path in path_strings:
        path_parse = parse_path(path)
        length = path_parse.length(error=1e-5)
        if length < (max(width / 500, 20)):
            continue
        num_points = 200
        point_arr = np.asarray([[int(round(path_parse.point(x).real)),int(round(path_parse.point(x).imag))]  for x in np.linspace(0, 1, num_points)], dtype=np.float32)
        print(point_arr.min(axis=0), point_arr.max(axis=0))
        if points == None:
            points = [{'points': point_arr, 'path': [path]}]
        # combining in loop
        grouped = False
        # for n, p in enumerate(points):
        #     pts = p['points']
        #     dist_arr = distance.cdist(pts, point_arr, 'euclidean')
        #     dist = dist_arr.min()
        #     if dist < width / 15:
        #         print("Combined")
        #         if groups is None:
        #             groups = [{'points': point_arr, 'paths': [path]}]
        #         else:
        #             for g in groups:
        #                 if p['path'] in g['paths']:
        #                     grouped = True
        #                     arr_1 = g['points']
        #                     g['points'] = np.concatenate((g['points'], point_arr))
        #                     g['paths'].append(path)
        #         break
        if grouped == False:
            if groups is None:
                groups = [{'points': point_arr, 'paths': [path]}]
            groups.append({'points': point_arr, 'paths': [path]})
        points.append({'points': point_arr, 'path': path})
    print("Combined groups ", len(groups))
    gl = 0
    for i in groups:
        gl += len(i['paths'])
    print(gl, len(path_strings))
    groups = combineGroups(groups, width, 200)
    words = combineWords(groups, width, 15)
    fixWordOrder(words)
    fixLetters(words)
    boxes = []
    image = cv2.imread(svg_path + os.sep + "extract.jpg")
    height= int(height * scale * 0.8)
    width = int(width * 0.8)
    print(len(groups))
    # formBoundaries(groups, image, scale, width, height)
    # formBoundaries(words, image, scale, width, height)
    gl = 0
    for i in words:
        gl += len(i['letters'])
    print(gl)
    print(len(words))
    image2 = copy.deepcopy(image)
    word_letters = []
    for ind, w in enumerate(words):
        tmp_folder = svg_path + "word-" + str(ind) + os.sep
        word_letters.append({'path': tmp_folder, 'len': len(w['letters'])})
        if not os.path.exists(tmp_folder):
            os.makedirs(tmp_folder)
        formBoundaries(w['letters'], image, scale, width, height, tmp_folder, image2)
    cv2.imwrite(svg_path + "line_detect.jpg", image2)
    print(word_letters)
    words = []
    for ww in word_letters:
        word = ''
        for l in range(ww['len']):
            char_path = ww['path'] + str(l) + ".jpg"
            prediction = classify.predict(char_path, model, mapping)
            word += prediction
        words.append(word)
    f = open(svg_path + 'prediction.txt', 'w')
    sentence = (" ").join(words)
    f.write(sentence)
    f.close()
    return sentence
    # print(stdout[-1])