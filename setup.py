import os.path
from setuptools import setup, find_packages

djl_url = "http://github.com/lacostej/nosyd"
version = "0.0.5"

changes_file = os.path.join(os.path.dirname(__file__), 'NEWS')
changes = file(changes_file).read().split('\n\n\n')
latest_changes = '\n\n\n'.join(changes[:3])

setup(
    name="Nosyd",
    version=version,
    description="""\
A _minimalist_ personal command line friendly CI server. Automatically runs your build whenever one
of the monitored files of the monitored projects has changed.
    """,
    long_description=open('README').read() + '\n\n' + latest_changes,
    license="MIT",
    author="Jeff Winkler & Jerome Lacoste",
    author_email="jerome.lacoste@gmail.com",
    url=djl_url,
    download_url="%(djl_url)s/tarball/%(version)s" % locals(),
    packages=find_packages(),
#    install_requires='xxx',
    extras_require= {
       'nose': ["nose"]
#      'Growl': 0.0.7
#      pynotify: ???
    },
    entry_points={'console_scripts':['nosyd = nosyd.nosyd:main']},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Environment :: X11 Applications :: Gnome',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.6',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Testing',
    ]

    )

# end of file
