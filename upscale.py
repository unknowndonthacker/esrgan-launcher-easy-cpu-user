
import math
import numpy as np
import torch
import rrdbnet

class Upscaler(object):
    def upscale(self, input_image):
        # nop
        return input_image

class RRDBNetUpscaler(Upscaler):
    def __init__(self, model, device):
        net, scale = model.load()

        model_net = rrdbnet.RRDBNet(3, 3, 64, 23)
        model_net.load_state_dict(net, scale, strict=True)
        model_net.eval()

        for _, v in model_net.named_parameters():
            v.requires_grad = False

        self.model = model_net.to(device)
        self.device = device
        self.scale_factor = 2 ** scale

    def upscale(self, input_image):
        input_image = input_image * 1.0 / 255
        input_image = np.transpose(input_image[:, :, [2, 1, 0]], (2, 0, 1))
        input_image = torch.from_numpy(input_image).float()
        input_image = input_image.unsqueeze(0).to(self.device)

        output_image = self.model(input_image).data.squeeze().float().cpu().clamp_(0, 1).numpy()
        output_image = np.transpose(output_image[[2, 1, 0], :, :], (1, 2, 0))
        output_image = (output_image * 255.0).round()

        return output_image

class TiledUpscaler(Upscaler):
    def __init__(self, upscaler, tile_size, tile_padding):
        self.upscaler = upscaler
        self.scale_factor = upscaler.scale_factor
        self.tile_size = tile_size
        self.tile_padding = tile_padding

    def upscale(self, input_image):
        scale_factor = self.upscaler.scale_factor
        width, height, depth = input_image.shape
        output_width = width * scale_factor
        output_height = height * scale_factor
        output_shape = (output_width, output_height, depth)

        # start with black image
        output_image = np.zeros(output_shape, np.uint8)

        tile_padding = math.ceil(self.tile_size * self.tile_padding)
        tile_size = math.ceil(self.tile_size / scale_factor)

        tiles_x = math.ceil(width / tile_size)
        tiles_y = math.ceil(height / tile_size)

        for y in range(tiles_y):
            for x in range(tiles_x):
                # extract tile from input image
                ofs_x = x * tile_size
                ofs_y = y * tile_size

                # input tile area on total image
                input_start_x = ofs_x
                input_end_x = min(ofs_x + tile_size, width)

                input_start_y = ofs_y
                input_end_y = min(ofs_y + tile_size, height)

                # input tile area on total image with padding
                input_start_x_pad = max(input_start_x - tile_padding, 0)
                input_end_x_pad = min(input_end_x + tile_padding, width)

                input_start_y_pad = max(input_start_y - tile_padding, 0)
                input_end_y_pad = min(input_end_y + tile_padding, height)

                # input tile dimensions
                input_tile_width = input_end_x - input_start_x
                input_tile_height = input_end_y - input_start_y

                tile_idx = y * tiles_x + x + 1

                print("  Tile %d/%d (x=%d y=%d %dx%d)" % \
                    (tile_idx, tiles_x * tiles_y, x, y, input_tile_width, input_tile_height))

                input_tile = input_image[input_start_x_pad:input_end_x_pad, input_start_y_pad:input_end_y_pad]

                # upscale tile
                output_tile = self.upscaler.upscale(input_tile)

                # output tile area on total image
                output_start_x = input_start_x * scale_factor
                output_end_x = input_end_x * scale_factor

                output_start_y = input_start_y * scale_factor
                output_end_y = input_end_y * scale_factor

                # output tile area without padding
                output_start_x_tile = (input_start_x - input_start_x_pad) * scale_factor
                output_end_x_tile = output_start_x_tile + input_tile_width * scale_factor

                output_start_y_tile = (input_start_y - input_start_y_pad) * scale_factor
                output_end_y_tile = output_start_y_tile + input_tile_height * scale_factor

                # put tile into output image
                output_image[output_start_x:output_end_x, output_start_y:output_end_y] = \
                    output_tile[output_start_x_tile:output_end_x_tile, output_start_y_tile:output_end_y_tile]

        return output_image
