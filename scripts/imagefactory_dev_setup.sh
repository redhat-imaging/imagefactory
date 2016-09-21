# N.B. Tested on Fedora 17 only.  Path's may change depending on your distro.

# Be sure to check these values are correct for your system.
PYTHON_PATH="/usr/lib/python2.7" 
IMAGEFACTORY_PLUGINS=/etc/imagefactory/plugins.d/

WORKING_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
IMAGEFACTORY_SRC=$(dirname "$WORKING_DIR")

sudo mkdir -p $IMAGEFACTORY_PLUGINS
sudo rm -f $IMAGEFACTORY_PLUGINS/*.info

# Create symlinks to src plugins
for plugin in $IMAGEFACTORY_SRC/imagefactory_plugins/*/*.info; do
    sudo ln -s "$plugin" $IMAGEFACTORY_PLUGINS
done

# Add Imagefactory src dirs to imgfacdev.pth
sudo sh -c "echo \"$IMAGEFACTORY_SRC\" > $PYTHON_PATH/site-packages/imgfacdev.pth"

echo "******************************************************"
echo "**    Imagefactory Development Environment Setup    **"
echo "**                                                  **"
echo "**             To start the server run:             **"
echo "**                                                  **"
echo "**         'sudo imagefactoryd --foreground'        **"
echo "**         # from imagefactory src directory        **"
echo "**                                                  **"
echo "**   For more options see: 'imagefactoryd --help'   **"
echo "******************************************************"
