from __future__ import absolute_import, division, print_function

import os
import sys
import glob
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))
import argparse
import numpy as np
import PIL.Image as pil
import matplotlib as mpl
import matplotlib.cm as cm
from core.R_MSFM import R_MSFM3,R_MSFM6
import torch
from torchvision import transforms, datasets

import networks
def disp_to_depth(disp, min_depth, max_depth):
    """Convert network's sigmoid output into depth prediction
    """
    min_disp = 1 / max_depth
    max_disp = 1 / min_depth
    scaled_disp = min_disp + (max_disp - min_disp) * disp
    depth = 1 / scaled_disp
    return scaled_disp, depth




def parse_args():
    parser = argparse.ArgumentParser(
        description='Simple testing funtion for R-MSFM models.')

    parser.add_argument('--image_path', type=str,
                        help='path to a test image or folder of images', required=True)

    parser.add_argument('--ext', type=str,
                        help='image extension to search for in folder', default="jpeg")
    parser.add_argument('--model_path', type=str,
                        help='path to a models.pth', default="./3M")
    parser.add_argument('--update', type=int,
                        help='iterative update', default=3)
    parser.add_argument("--no_cuda",
                        help='if set, disables CUDA',
                        action='store_true')
    parser.add_argument("--x",
                        help='if set, R-MSFMX',
                        action='store_true')
    # a = ['--image_path', './a',  '--model_path',  './3M_gc_1024',  '--update', '3' ]
    return parser.parse_args()


def test_simple(args):
    """Function to predict for a single image or folder of images
    """
    # assert args.model_name is not None, \
    #     "You must specify the --model_name parameter; see README.md for an example"

    if torch.cuda.is_available() and not args.no_cuda:
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    # download_model_if_doesnt_exist(args.model_name)
    model_path = args.model_path
    print("-> Loading model from ", model_path)
    encoder_path = os.path.join(model_path, "encoder.pth")
    depth_decoder_path = os.path.join(model_path, "depth.pth")



    # LOADING PRETRAINED MODEL
    print("   Loading pretrained encoder")
    if args.x:
        encoder = networks.ResnetEncoder(50, False)
    else:
        encoder = networks.ResnetEncoder(18, False)
    encoder .load_state_dict(torch.load(encoder_path, map_location= device),False)
    encoder.to(device)
    encoder.eval()

    print("   Loading pretrained decoder")
    if args.update == 3:
        depth_decoder = R_MSFM3(args.x)
    else:
        depth_decoder = R_MSFM6(args.x)
    depth_decoder.load_state_dict(torch.load(depth_decoder_path, map_location= device))
    depth_decoder.to(device)
    depth_decoder.eval()

    # FINDING INPUT IMAGES
    if os.path.isfile(args.image_path):
        # Only testing on a single image
        paths = [args.image_path]
        output_directory = os.path.dirname(args.image_path)
    elif os.path.isdir(args.image_path):
        # Searching folder for images
        print(f"Searching for images in directory: {args.image_path}")
        search_pattern = os.path.join(args.image_path, '*.{}'.format(args.ext))
        print(f"Search pattern: {search_pattern}")
        paths = glob.glob(search_pattern)
        print(f"Found {len(paths)} images: {paths}")
        output_directory = args.image_path
    else:
        raise Exception("Can not find args.image_path: {}".format(args.image_path))

    print("-> Predicting on {:d} test images".format(len(paths)))

    # PREDICTING ON EACH IMAGE IN TURN
    with torch.no_grad():
        for idx, image_path in enumerate(paths):

            if image_path.endswith("_disp.jpg"):
                # don't try to predict disparity for a disparity image!
                continue
            feed_width = 640
            feed_height = 192
            # Load image and preprocess
            input_image = pil.open(image_path).convert('RGB')
            original_width, original_height = input_image.size
            input_image = input_image.resize((feed_width, feed_height), pil.LANCZOS)
            input_image = transforms.ToTensor()(input_image).unsqueeze(0)

            # PREDICTION
            input_image = input_image.to(device)
            features = encoder(input_image)
            outputs = depth_decoder(features)


            if args.update == 3:
                disp = outputs[("disp_up", 2)]
            else:
                disp = outputs[("disp_up", 5)]
            disp_resized = torch.nn.functional.interpolate(
                disp, (original_height, original_width), mode="bilinear", align_corners=False)

            # Saving numpy file
            output_name = os.path.splitext(os.path.basename(image_path))[0]
            npy_output_directory = "C:/Users/dinbin/Desktop/深度估计/深度估计/R-MSFM-main/test_images/效果图2"
            jpg_output_directory = "C:/Users/dinbin/Desktop/深度估计/深度估计/R-MSFM-main/test_images/效果图"
            
            # Create output directories if they don't exist
            os.makedirs(npy_output_directory, exist_ok=True)
            os.makedirs(jpg_output_directory, exist_ok=True)
            
            name_dest_npy = os.path.join(npy_output_directory, "{}_disp.npy".format(output_name))
            scaled_disp, _ = disp_to_depth(disp, 0.1, 100)
            np.save(name_dest_npy, scaled_disp.cpu().numpy())
            
            # Saving colormapped depth image
            disp_resized_np = disp_resized.squeeze().cpu().numpy()
            vmax = np.percentile(disp_resized_np, 95)
            normalizer = mpl.colors.Normalize(vmin=disp_resized_np.min(), vmax=vmax)
            mapper = cm.ScalarMappable(norm=normalizer, cmap='magma')
            colormapped_im = (mapper.to_rgba(disp_resized_np)[:, :, :3] * 255).astype(np.uint8)
            
            im = pil.fromarray(colormapped_im)
            name_dest_im = os.path.join(jpg_output_directory, "{}_disp.jpeg".format(output_name))
            im.save(name_dest_im)

            print("   Processed {:d} of {:d} images - saved prediction to {}".format(
                idx + 1, len(paths), name_dest_im))

    print('-> Done!')


if __name__ == '__main__':
    args = parse_args()
    test_simple(args)

